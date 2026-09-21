from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from common.models import TimestampedModel, UUIDModel


class Role(models.TextChoices):
    """RBAC roles. The capability matrix lives in REQUIREMENTS.md section 5 and
    is enforced by permission classes plus a service-layer re-check for
    sensitive actions."""

    OWNER = "OWNER", "Owner"
    MANAGER = "MANAGER", "Manager"
    RECEPTIONIST = "RECEPTIONIST", "Receptionist"


class AdminUserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra):
        if not email:
            raise ValueError("Admin users require an email address")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("role", Role.OWNER)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class AdminUser(UUIDModel, TimestampedModel, AbstractBaseUser, PermissionsMixin):
    """Staff account. Customers are not users -- they never log in (see
    apps.customers.Customer)."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.RECEPTIONIST)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # MFA is mandatory for OWNER and strongly recommended for MANAGER. The TOTP
    # secret itself lives in the secret manager; only its reference is stored.
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_ref = models.CharField(max_length=255, blank=True)

    last_login_at = models.DateTimeField(null=True, blank=True)
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    objects = AdminUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "admin_user"

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    @property
    def requires_mfa(self) -> bool:
        return self.role == Role.OWNER


class LoginAttempt(UUIDModel, TimestampedModel):
    """Feeds login throttling and the admin brute-force alert."""

    email = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(default=False)

    class Meta:
        db_table = "login_attempt"
        indexes = [models.Index(fields=["email", "created_at"])]


class AdminSession(UUIDModel, TimestampedModel):
    """A signed-in owner-panel session, presented as a bearer token.

    Bearer rather than a cookie because the site and the API live on different
    registrable domains (each `*.vercel.app` host is its own site), where a
    session cookie is third-party and browsers increasingly drop it.

    Only the SHA-256 of the token is stored: a leaked database dump must not
    hand out working sessions.
    """

    user = models.ForeignKey(AdminUser, on_delete=models.CASCADE, related_name="sessions")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "admin_session"
        indexes = [models.Index(fields=["user", "expires_at"])]

    def __str__(self) -> str:
        return f"session for {self.user_id} until {self.expires_at:%Y-%m-%d %H:%M}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()
