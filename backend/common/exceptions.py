"""Domain exceptions and a uniform API error envelope.

Domain services raise these; they know nothing about HTTP. The DRF handler maps
them to status codes at the edge.
"""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from common.context import get_request_id

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Base class for business-rule failures."""

    code = "domain_error"
    http_status = status.HTTP_400_BAD_REQUEST
    message = "The request could not be completed."
    # Context keys that may be returned to the client as error.details. Empty
    # by default: context is for logs and often holds internal state.
    public_context: tuple[str, ...] = ()

    def __init__(self, message: str | None = None, **context):
        self.message = message or self.message
        self.context = context
        super().__init__(self.message)


class ValidationFailed(DomainError):
    code = "validation_failed"
    http_status = status.HTTP_400_BAD_REQUEST


class NotFound(DomainError):
    code = "not_found"
    http_status = status.HTTP_404_NOT_FOUND
    message = "Not found."


class PermissionDenied(DomainError):
    code = "permission_denied"
    http_status = status.HTTP_403_FORBIDDEN
    message = "You do not have permission to perform this action."


class ConflictError(DomainError):
    code = "conflict"
    http_status = status.HTTP_409_CONFLICT


class CapacityExhausted(DomainError):
    """Today's promotional capacity is fully taken."""

    code = "capacity_exhausted"
    http_status = status.HTTP_409_CONFLICT
    message = "Today's promotion is full."


class CampaignLocked(DomainError):
    """Today's campaign has a paid participant; config is immutable."""

    code = "campaign_locked"
    http_status = status.HTTP_409_CONFLICT
    message = "Today's campaign is locked. Changes will apply from the next campaign date."


class PaymentError(DomainError):
    code = "payment_error"
    http_status = status.HTTP_402_PAYMENT_REQUIRED


class SignatureInvalid(PaymentError):
    code = "signature_invalid"
    http_status = status.HTTP_400_BAD_REQUEST
    message = "Payment could not be verified."


class ReauthRequired(DomainError):
    code = "reauth_required"
    http_status = status.HTTP_403_FORBIDDEN
    message = "Re-authentication is required for this action."


def api_exception_handler(exc, context):
    """Uniform error envelope: {"error": {"code", "message", "request_id"}}.

    Domain errors carry a stable machine-readable code so the frontend can react
    (e.g. show the 'promotion full' state) without string-matching messages.
    """
    if isinstance(exc, DomainError):
        logger.info(
            "domain_error",
            extra={"code": exc.code, "detail": exc.message, **exc.context},
        )
        error = {
            "code": exc.code,
            "message": exc.message,
            "request_id": get_request_id(),
        }
        details = {k: exc.context[k] for k in exc.public_context if k in exc.context}
        if details:
            error["details"] = details
        return Response({"error": error}, status=exc.http_status)

    if isinstance(exc, DjangoValidationError):
        return Response(
            {
                "error": {
                    "code": "validation_failed",
                    "message": "; ".join(exc.messages),
                    "request_id": get_request_id(),
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, IntegrityError):
        # Unique constraints are the idempotency mechanism in this system
        # (REQUIREMENTS.md 3.4). Hitting one is usually a duplicate request,
        # not a server fault.
        logger.warning("integrity_error", exc_info=exc)
        return Response(
            {
                "error": {
                    "code": "conflict",
                    "message": "This request conflicts with an existing record.",
                    "request_id": get_request_id(),
                }
            },
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, DRFValidationError):
        # Serializer rejections are ordinary bad input, so they carry the same
        # machine-readable code as our own ValidationFailed. Without this they
        # arrive as a generic "request_failed" and the frontend cannot tell a
        # form error from a server fault.
        return Response(
            {
                "error": {
                    "code": "validation_failed",
                    "message": _first_message(exc.detail),
                    "request_id": get_request_id(),
                    "fields": exc.detail if isinstance(exc.detail, dict) else None,
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = {
            "error": {
                "code": "request_failed",
                "message": response.data
                if isinstance(response.data, str)
                else _first_message(response.data),
                "request_id": get_request_id(),
            }
        }
    return response


def _first_message(data) -> str:
    if isinstance(data, dict):
        for value in data.values():
            return _first_message(value)
    if isinstance(data, list) and data:
        return _first_message(data[0])
    return str(data)
