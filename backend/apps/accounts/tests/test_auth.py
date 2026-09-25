"""Owner-panel sign-in: sessions, lockout and password changes."""

from __future__ import annotations

import datetime as dt
import json

import pytest
from django.utils import timezone

from apps.accounts.models import AdminSession, AdminUser, LoginAttempt, Role
from apps.accounts.services import hash_token
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db

PASSWORD = "a long owner passphrase 42"


@pytest.fixture(autouse=True)
def _fast_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def owner() -> AdminUser:
    return AdminUser.objects.create_user(
        email="owner@test.example", password=PASSWORD, full_name="Owner", role=Role.OWNER
    )


def login(client, email, password, **extra):
    return client.post(
        "/api/v1/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
        **extra,
    )


def bearer(token):
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def test_sign_in_returns_a_token_that_works(client, owner):
    r = login(client, "Owner@Test.Example ", PASSWORD)  # case and spaces forgiven
    assert r.status_code == 200
    body = r.json()
    assert body["user"] == {
        "email": "owner@test.example",
        "full_name": "Owner",
        "role": "OWNER",
        "mfa_enabled": False,
    }

    me = client.get("/api/v1/auth/me", **bearer(body["token"]))
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "owner@test.example"


def test_only_the_token_hash_is_stored(client, owner):
    token = login(client, owner.email, PASSWORD).json()["token"]
    session = AdminSession.objects.get()
    assert session.token_hash == hash_token(token)
    assert token not in session.token_hash
    assert AuditLog.objects.filter(action="auth.login").count() == 1


def test_wrong_password_and_unknown_email_get_the_same_answer(client, owner):
    wrong = login(client, owner.email, "not it")
    unknown = login(client, "nobody@test.example", "not it")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_credentials"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_five_failures_lock_that_network_even_against_the_right_password(client, owner):
    for _ in range(5):
        assert login(client, owner.email, "wrong").status_code == 401

    locked = login(client, owner.email, PASSWORD)
    assert locked.status_code == 423
    assert locked.json()["error"]["code"] == "account_locked"


def test_a_stranger_cannot_lock_the_owner_out_of_their_own_network(client, owner, settings):
    """The lock is per (email, network). An attacker failing from their own
    connection must not stop the owner signing in from the salon's."""
    settings.TRUST_X_REAL_IP = True
    for _ in range(6):
        login(client, owner.email, "wrong", HTTP_X_REAL_IP="203.0.113.66")

    assert login(client, owner.email, PASSWORD, HTTP_X_REAL_IP="198.51.100.7").status_code == 200
    owner.refresh_from_db()
    assert not owner.is_locked


def test_the_lock_answer_does_not_reveal_whether_an_account_exists(client, owner):
    # One address per email keeps the per-IP request throttle out of the way.
    addresses = {owner.email: "10.0.0.1", "nobody@test.example": "10.0.0.2"}
    for email, address in addresses.items():
        for _ in range(5):
            login(client, email, "wrong", REMOTE_ADDR=address)
    real = login(client, owner.email, "wrong", REMOTE_ADDR="10.0.0.1")
    fake = login(client, "nobody@test.example", "wrong", REMOTE_ADDR="10.0.0.2")
    assert real.status_code == fake.status_code == 423
    assert real.json()["error"]["message"] == fake.json()["error"]["message"]


def test_the_lock_lifts_when_it_expires(client, owner):
    AdminUser.objects.filter(pk=owner.pk).update(
        locked_until=timezone.now() - dt.timedelta(seconds=1)
    )
    assert login(client, owner.email, PASSWORD).status_code == 200
    owner.refresh_from_db()
    assert owner.locked_until is None and owner.failed_login_count == 0


def test_a_success_resets_the_failure_count(client, owner):
    for _ in range(4):
        login(client, owner.email, "wrong")
    assert login(client, owner.email, PASSWORD).status_code == 200
    for _ in range(4):
        assert login(client, owner.email, "wrong").status_code == 401
    assert login(client, owner.email, PASSWORD).status_code == 200


def test_many_failures_from_one_ip_block_that_ip(client, owner, settings):
    """Spraying passwords across many accounts is stopped per IP. Seeded
    directly, because the request throttle would otherwise answer first."""
    LoginAttempt.objects.bulk_create(
        [
            LoginAttempt(email=f"guess{i}@test.example", ip_address="127.0.0.1", success=False)
            for i in range(settings.LOGIN_IP_MAX_FAILURES)
        ]
    )
    r = login(client, owner.email, PASSWORD)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "too_many_attempts"


def test_x_real_ip_is_ignored_unless_trusted(client, owner, settings):
    settings.TRUST_X_REAL_IP = False
    login(client, owner.email, "wrong", HTTP_X_REAL_IP="203.0.113.9")
    settings.TRUST_X_REAL_IP = True
    login(client, owner.email, "wrong", HTTP_X_REAL_IP="203.0.113.9")
    assert list(
        LoginAttempt.objects.order_by("created_at").values_list("ip_address", flat=True)
    ) == [
        "127.0.0.1",
        "203.0.113.9",
    ]


def test_inactive_accounts_cannot_sign_in(client, owner):
    AdminUser.objects.filter(pk=owner.pk).update(is_active=False)
    assert login(client, owner.email, PASSWORD).status_code == 401


def test_sign_out_ends_the_session(client, owner):
    token = login(client, owner.email, PASSWORD).json()["token"]
    assert client.post("/api/v1/auth/logout", **bearer(token)).status_code == 200
    assert client.get("/api/v1/auth/me", **bearer(token)).status_code == 401


def test_an_expired_session_is_refused(client, owner):
    token = login(client, owner.email, PASSWORD).json()["token"]
    AdminSession.objects.update(expires_at=timezone.now() - dt.timedelta(seconds=1))
    assert client.get("/api/v1/auth/me", **bearer(token)).status_code == 401


def test_no_token_and_a_garbage_token_are_refused(client, owner):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", **bearer("not-a-real-token")).status_code == 401


def test_a_session_ends_when_the_account_is_locked(client, owner):
    token = login(client, owner.email, PASSWORD).json()["token"]
    AdminUser.objects.filter(pk=owner.pk).update(
        locked_until=timezone.now() + dt.timedelta(minutes=5)
    )
    assert client.get("/api/v1/auth/me", **bearer(token)).status_code == 401


def _change(client, token, current, new):
    return client.post(
        "/api/v1/auth/password",
        data=json.dumps({"current_password": current, "new_password": new}),
        content_type="application/json",
        **bearer(token),
    )


def test_changing_the_password_signs_out_every_other_session(client, owner):
    other = login(client, owner.email, PASSWORD).json()["token"]
    mine = login(client, owner.email, PASSWORD).json()["token"]

    r = _change(client, mine, PASSWORD, "a different long passphrase 7")
    assert r.status_code == 200

    assert client.get("/api/v1/auth/me", **bearer(mine)).status_code == 200
    assert client.get("/api/v1/auth/me", **bearer(other)).status_code == 401
    assert login(client, owner.email, "a different long passphrase 7").status_code == 200
    assert AuditLog.objects.filter(action="auth.password_changed").count() == 1


def test_password_change_checks_the_current_password(client, owner):
    token = login(client, owner.email, PASSWORD).json()["token"]
    r = _change(client, token, "not it", "a different long passphrase 7")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "reauth_failed"
    # The session survives a mistyped password.
    assert client.get("/api/v1/auth/me", **bearer(token)).status_code == 200
    owner.refresh_from_db()
    assert owner.check_password(PASSWORD)


def test_repeated_wrong_reauth_passwords_lock_the_account_and_end_the_session(client, owner):
    """A stolen session must not be able to brute-force the password that
    guards the payment QR."""
    token = login(client, owner.email, PASSWORD).json()["token"]
    for _ in range(5):
        _change(client, token, "guess", "a different long passphrase 7")

    owner.refresh_from_db()
    assert owner.is_locked
    assert client.get("/api/v1/auth/me", **bearer(token)).status_code == 401


def test_password_change_rejects_a_weak_password(client, owner):
    token = login(client, owner.email, PASSWORD).json()["token"]
    r = _change(client, token, PASSWORD, "12345")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_failed"
