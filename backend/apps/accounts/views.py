from __future__ import annotations

from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import services
from apps.accounts.authentication import AdminTokenAuthentication
from apps.accounts.permissions import IsOwner, IsOwnerOrManager, IsSignedIn


def _iso(value) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def serialize_user(user) -> dict:
    return {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "mfa_enabled": user.mfa_enabled,
    }


class SignedInView(APIView):
    """Base for owner-panel endpoints: bearer session, any staff role."""

    authentication_classes = (AdminTokenAuthentication,)
    permission_classes = (IsSignedIn,)
    throttle_scope = "owner"


class ManagerView(SignedInView):
    """Owner or manager: catalogue and content management."""

    permission_classes = (IsOwnerOrManager,)


class OwnerView(SignedInView):
    permission_classes = (IsOwner,)


class _LoginSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class LoginView(APIView):
    """POST /auth/login -> {token, expires_at, user}."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_scope = "admin_login"

    def post(self, request):
        data = _LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        session, token = services.login(
            request,
            email=data.validated_data["email"],
            password=data.validated_data["password"],
        )
        return Response(
            {
                "token": token,
                "expires_at": _iso(session.expires_at),
                "user": serialize_user(session.user),
            }
        )


class LogoutView(SignedInView):
    def post(self, request):
        services.logout(request.auth, request)
        return Response({"signed_out": True})


class MeView(SignedInView):
    def get(self, request):
        return Response(
            {"user": serialize_user(request.user), "expires_at": _iso(request.auth.expires_at)}
        )


class _PasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=256, trim_whitespace=False)
    new_password = serializers.CharField(max_length=256, trim_whitespace=False)


class ChangePasswordView(SignedInView):
    def post(self, request):
        data = _PasswordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.change_password(
            request.user,
            request.auth,
            current_password=data.validated_data["current_password"],
            new_password=data.validated_data["new_password"],
            request=request,
        )
        return Response({"password_changed": True})
