"""Owner-panel sign-in.

Brute-force protection lives in the database, not the cache: the DRF throttle
fails open when the cache is down (common/throttling.py), which is the right
trade for public pages and the wrong one for a password form. Limits:

* per (email, IP) -- LOGIN_MAX_FAILURES failures in LOGIN_LOCKOUT_MINUTES
  refuse that email from that network, even with the right password. Keyed
  by network so an attacker cannot lock the owner out of their own phone, and
  counted for any email so the answer never reveals which accounts exist;
* per IP -- LOGIN_IP_MAX_FAILURES failures across any accounts in that window;
* re-authentication -- wrong passwords typed by someone already signed in
  (payment QR changes, password change) lock the account itself.

Transactions are explicit here (ATOMIC_REQUESTS is off), so a failure is
counted in its own committed transaction before the error is raised; raising
inside the block would roll the count back and make the lockout unreachable.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import AdminSession, AdminUser, LoginAttempt
from apps.audit.services import record
from common.exceptions import DomainError, ValidationFailed
from common.http import client_ip
from common.tokens import opaque_token

logger = logging.getLogger(__name__)


class InvalidCredentials(DomainError):
    code = "invalid_credentials"
    http_status = status.HTTP_401_UNAUTHORIZED
    # One message for an unknown email and a wrong password, so the form
    # cannot be used to discover which addresses have accounts.
    message = "Email or password is incorrect."


class AccountLocked(DomainError):
    code = "account_locked"
    http_status = status.HTTP_423_LOCKED
    message = "Too many failed attempts. Try again in 15 minutes."


class ReauthFailed(DomainError):
    """A signed-in user re-entered the wrong password for a sensitive action.

    403, not 401: the session is still valid, and a client that treats every
    401 as "signed out" must not throw the owner out over a typo.
    """

    code = "reauth_failed"
    http_status = status.HTTP_403_FORBIDDEN
    message = "Your password is incorrect."


class TooManyAttempts(DomainError):
    code = "too_many_attempts"
    http_status = status.HTTP_429_TOO_MANY_REQUESTS
    message = "Too many failed sign-in attempts from this network. Try again later."


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _window_start() -> dt.datetime:
    return timezone.now() - dt.timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)


def _record_attempt(email: str, request, success: bool) -> None:
    LoginAttempt.objects.create(
        email=email[:254],
        ip_address=client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
        success=success,
    )


def login(request, *, email: str, password: str) -> tuple[AdminSession, str]:
    """Check the credentials and open a session. Returns (session, raw token).

    The raw token is returned exactly once, here; only its hash is kept.
    """
    email = (email or "").strip().lower()
    ip = client_ip(request)

    if ip and (
        LoginAttempt.objects.filter(
            ip_address=ip, success=False, created_at__gte=_window_start()
        ).count()
        >= settings.LOGIN_IP_MAX_FAILURES
    ):
        logger.warning("login_ip_limited", extra={"ip": ip})
        raise TooManyAttempts()

    # Per (email, IP), counted from the attempts table for ANY email: the
    # answer is identical whether or not the account exists (no enumeration),
    # and a stranger failing from their own network cannot lock the real owner
    # out of theirs. An account-wide lock here would be a free denial of
    # service against the one person who confirms payments.
    # Failures since this pair's last success, like the "consecutive failures"
    # of a classic lockout: signing in clears the slate.
    since = _window_start()
    last_success = (
        LoginAttempt.objects.filter(email=email, ip_address=ip, success=True, created_at__gte=since)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    if last_success is not None:
        since = last_success
    if (
        LoginAttempt.objects.filter(
            email=email, ip_address=ip, success=False, created_at__gt=since
        ).count()
        >= settings.LOGIN_MAX_FAILURES
    ):
        _record_attempt(email, request, success=False)
        raise AccountLocked()

    # Locked by repeated wrong passwords on a re-authenticated action (see
    # register_reauth_failure) -- only reachable by someone who had a session.
    existing = AdminUser.objects.filter(email=email).first()
    if existing is not None and existing.is_locked:
        _record_attempt(email, request, success=False)
        raise AccountLocked()

    # authenticate() also spends the hashing time for an unknown email, so a
    # response's timing does not reveal whether the account exists.
    user = authenticate(request, email=email, password=password or "")

    if user is None:
        _record_attempt(email, request, success=False)
        raise InvalidCredentials()

    raw = opaque_token()
    now = timezone.now()
    with transaction.atomic():
        AdminUser.objects.filter(pk=user.pk).update(
            failed_login_count=0, locked_until=None, last_login_at=now, last_login=now
        )
        session = AdminSession.objects.create(
            user=user,
            token_hash=hash_token(raw),
            expires_at=now + dt.timedelta(hours=settings.ADMIN_SESSION_TTL_HOURS),
            ip_address=ip,
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
        )
        _record_attempt(email, request, success=True)
        record("auth.login", actor=user, entity=session, request=request)
    return session, raw


def logout(session: AdminSession, request) -> None:
    with transaction.atomic():
        AdminSession.objects.filter(pk=session.pk, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        record("auth.logout", actor=session.user, entity=session, request=request)


def change_password(
    user: AdminUser,
    session: AdminSession,
    *,
    current_password: str,
    new_password: str,
    request,
) -> None:
    """Replace the password and sign out every other session.

    Keeping the caller's own session is a convenience; ending the others is the
    point -- whoever might have had the old password loses access now.
    """
    if not user.check_password(current_password or ""):
        register_reauth_failure(user)
        raise ReauthFailed("Your current password is incorrect.")
    try:
        validate_password(new_password or "", user)
    except DjangoValidationError as exc:
        raise ValidationFailed(" ".join(exc.messages)) from exc

    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        revoked = (
            AdminSession.objects.filter(user=user, revoked_at__isnull=True)
            .exclude(pk=session.pk)
            .update(revoked_at=timezone.now())
        )
        record(
            "auth.password_changed",
            actor=user,
            entity=user,
            after={"other_sessions_revoked": revoked},
            request=request,
        )


def register_reauth_failure(user: AdminUser) -> None:
    """Count a wrong password typed by someone who is already signed in.

    This is the one lockout that is safe to apply account-wide: only a holder
    of a valid session can trigger it. At LOGIN_MAX_FAILURES the account locks,
    which also ends every session (AdminTokenAuthentication refuses a locked
    account) -- a stolen session cannot brute-force the password that guards
    the payment QR. Committed in its own transaction so the caller's error
    cannot roll the count back.
    """
    with transaction.atomic():
        locked = AdminUser.objects.select_for_update().get(pk=user.pk)
        locked.failed_login_count += 1
        fields = ["failed_login_count", "updated_at"]
        if locked.failed_login_count >= settings.LOGIN_MAX_FAILURES:
            locked.locked_until = timezone.now() + dt.timedelta(
                minutes=settings.LOGIN_LOCKOUT_MINUTES
            )
            locked.failed_login_count = 0
            fields.append("locked_until")
            logger.warning("admin_account_locked_reauth", extra={"user_id": str(locked.pk)})
        locked.save(update_fields=fields)


def confirm_password(user: AdminUser, password: str) -> None:
    """Re-authentication for actions that decide where customers' money goes."""
    if not user.check_password(password or ""):
        register_reauth_failure(user)
        raise ReauthFailed()
    if user.failed_login_count:
        AdminUser.objects.filter(pk=user.pk).update(failed_login_count=0)
