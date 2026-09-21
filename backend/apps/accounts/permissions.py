from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.accounts.models import Role


class IsSignedIn(BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(request.user and getattr(request.user, "is_authenticated", False))


class IsOwner(IsSignedIn):
    """OWNER only. REQUIREMENTS.md section 5 gives payment configuration --
    where customers' money goes -- to the owner alone."""

    message = "Only the salon owner can do this."

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and request.user.role == Role.OWNER
