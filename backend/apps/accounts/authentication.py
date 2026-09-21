from __future__ import annotations

import datetime as dt

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import AdminSession
from apps.accounts.services import hash_token

# Writing last_used_at on every request would turn each read into a write;
# once every few minutes is enough to see which sessions are alive.
_TOUCH_INTERVAL = dt.timedelta(minutes=5)


class AdminTokenAuthentication(BaseAuthentication):
    """`Authorization: Bearer <token>` against an unexpired, unrevoked session.

    Returns (user, session) so views can reach the session for logout and
    password changes.
    """

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b"bearer":
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Invalid authorization header.")

        try:
            raw = parts[1].decode()
        except UnicodeDecodeError as exc:
            raise AuthenticationFailed("Invalid authorization header.") from exc

        now = timezone.now()
        session = (
            AdminSession.objects.select_related("user")
            .filter(token_hash=hash_token(raw), revoked_at__isnull=True, expires_at__gt=now)
            .first()
        )
        if session is None:
            raise AuthenticationFailed("Your session has ended. Please sign in again.")

        user = session.user
        if not user.is_active or user.is_locked:
            raise AuthenticationFailed("This account cannot sign in right now.")

        if session.last_used_at is None or now - session.last_used_at > _TOUCH_INTERVAL:
            AdminSession.objects.filter(pk=session.pk).update(last_used_at=now)

        return (user, session)

    def authenticate_header(self, request) -> str:
        return 'Bearer realm="owner"'
