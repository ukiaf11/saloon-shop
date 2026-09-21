from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseNotModified
from django.views.decorators.http import require_GET
from rest_framework import serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.views import OwnerView
from apps.orders.serializers import lucky_block, serialize_order
from apps.orders.views import order_for_display
from apps.payments import services
from apps.payments.models import Payment, PaymentStatus
from apps.promotions.services import salon_today
from apps.salons.models import Salon
from common.exceptions import NotFound, ValidationFailed


def _active_salon() -> Salon:
    salon = Salon.objects.filter(status=Salon.Status.ACTIVE).first()
    if salon is None:
        raise NotFound("Salon is not available.")
    return salon


def _iso(value) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _qr_version(row) -> str:
    return row.qr_sha256[:16]


# --- public ------------------------------------------------------------------


def serialize_options(salon) -> dict:
    row = services.get_settings(salon)
    method = services.payment_method(salon, row)
    upi = None
    if method == services.PaymentMethod.UPI_QR:
        upi = {
            # A content hash, so the image URL changes exactly when the QR does
            # and can otherwise be cached forever.
            "qr_image_version": _qr_version(row),
            "upi_id": row.upi_id or None,
            "payee_name": row.payee_name or None,
        }
    return {"method": method, "upi_qr": upi}


class PaymentOptionsView(APIView):
    """GET /payments/options -- how a customer can pay right now."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_scope = "public_read"

    def get(self, request):
        return Response(serialize_options(_active_salon()))


@require_GET
def qr_image(request):
    """GET /payments/qr-image -- the salon's QR, re-encoded PNG bytes.

    A plain view, not DRF: the API's renderers speak JSON only.
    """
    salon = Salon.objects.filter(status=Salon.Status.ACTIVE).first()
    row = services.get_settings(salon, with_image=True) if salon else None
    if row is None or not row.has_qr or not row.qr_image:
        return HttpResponse(status=404)

    etag = f'"{row.qr_sha256}"'
    if request.headers.get("If-None-Match") == etag:
        return HttpResponseNotModified()

    response = HttpResponse(bytes(row.qr_image), content_type=row.qr_content_type or "image/png")
    response["ETag"] = etag
    response["Content-Disposition"] = 'inline; filename="payment-qr.png"'
    if request.GET.get("v") == _qr_version(row):
        # Versioned URL: the bytes behind it can never change.
        response["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response["Cache-Control"] = "public, max-age=60"
    return response


class _ClaimSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=40)


class UpiClaimView(APIView):
    """POST /orders/{id}/upi-payment -- "I have paid, here is the UTR".

    Guarded, like GET /orders/{id}, by the unguessability of the order UUID.
    """

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_scope = "upi_claim"

    def post(self, request, order_id):
        data = _ClaimSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.submit_upi_claim(order_id, data.validated_data["reference"])
        return Response(serialize_order(order_for_display(order_id)))


# --- owner -------------------------------------------------------------------


def serialize_settings(salon) -> dict:
    row = services.get_settings(salon)
    return {
        "method": services.payment_method(salon, row),
        "gateway_configured": services.gateway_configured(salon),
        "qr": (
            {
                "version": _qr_version(row),
                "width": row.qr_width,
                "height": row.qr_height,
                "updated_at": _iso(row.qr_updated_at),
            }
            if row is not None and row.has_qr
            else None
        ),
        "upi_id": row.upi_id if row else "",
        "payee_name": row.payee_name if row else "",
    }


class OwnerPaymentSettingsView(OwnerView):
    """GET/PUT /owner/payment-settings. PUT takes multipart so a QR image can
    ride along with the text fields; every change needs the password again."""

    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get(self, request):
        return Response(serialize_settings(_active_salon()))

    def put(self, request):
        salon = _active_salon()
        data = request.data

        def text(name):
            value = data.get(name)
            return None if value is None else str(value)

        qr_file = request.FILES.get("qr_image")
        remove = str(data.get("remove_qr", "")).lower() in ("1", "true", "yes")
        if qr_file is not None and remove:
            raise ValidationFailed("Upload a new QR or remove the current one, not both.")

        services.update_payment_settings(
            salon,
            actor=request.user,
            password=text("password") or "",
            qr_file=qr_file,
            remove_qr=remove,
            upi_id=text("upi_id"),
            payee_name=text("payee_name"),
            request=request,
        )
        return Response(serialize_settings(salon))


_STATUS_FILTER = {
    "awaiting": PaymentStatus.AWAITING_CONFIRMATION,
    "confirmed": PaymentStatus.CONFIRMED,
    "rejected": PaymentStatus.REJECTED,
}
_LIST_LIMIT = 100


def serialize_owner_payment(payment: Payment, today) -> dict:
    order = payment.order
    try:
        hold = order.slot_reservation
    except ObjectDoesNotExist:
        hold = None
    refund = next(iter(order.refunds.all()), None)
    draw = lucky_block(order)
    return {
        "id": str(payment.id),
        "status": payment.status.lower(),
        "reference": payment.reference,
        "amount_paise": payment.amount_paise,
        "submitted_at": _iso(payment.submitted_at),
        "decided_at": _iso(payment.decided_at),
        "rejection_reason": payment.rejection_reason or None,
        "order": {
            "id": str(order.id),
            "public_order_number": order.public_order_number,
            "status": order.status,
            "total_paise": order.total_paise,
            "created_at": _iso(order.created_at),
            "items": [
                {"name": item.service_name_snapshot, "quantity": item.quantity}
                for item in order.items.all()
            ],
        },
        # The owner sees the full number: they may need to call the customer,
        # or send a refund to it.
        "customer": {"name": order.customer.name, "phone": order.customer.phone},
        "draw": draw,
        # A claim held for a day that has ended will be confirmed as paid but
        # cannot join that day's draw any more. The panel warns before it happens.
        "draw_day_over": bool(
            draw["status"] == "held"
            and hold is not None
            and hold.daily_campaign.campaign_date < today
        ),
        "refund": (
            {
                "id": str(refund.id),
                "amount_paise": refund.amount_paise,
                "status": refund.status.lower(),
                "method": refund.method or None,
                "reference": refund.reference or None,
            }
            if refund
            else None
        ),
    }


class OwnerPaymentsView(OwnerView):
    """GET /owner/payments?status=awaiting|confirmed|rejected"""

    def get(self, request):
        salon = _active_salon()
        key = request.query_params.get("status", "awaiting")
        if key not in _STATUS_FILTER:
            raise ValidationFailed("status must be awaiting, confirmed or rejected.")
        payments = (
            Payment.objects.filter(salon=salon, status=_STATUS_FILTER[key])
            .select_related(
                "order__customer",
                "order__lucky_decision__daily_campaign",
                "order__slot_reservation__daily_campaign",
            )
            .prefetch_related("order__items", "order__refunds")
            .order_by("-submitted_at")[:_LIST_LIMIT]
        )
        today = salon_today(salon)
        return Response({"results": [serialize_owner_payment(p, today) for p in payments]})


def _decided(payment_id, salon) -> dict:
    payment = (
        Payment.objects.select_related(
            "order__customer",
            "order__lucky_decision__daily_campaign",
            "order__slot_reservation__daily_campaign",
        )
        .prefetch_related("order__items", "order__refunds")
        .get(pk=payment_id)
    )
    return serialize_owner_payment(payment, salon_today(salon))


class OwnerConfirmPaymentView(OwnerView):
    def post(self, request, payment_id):
        salon = _active_salon()
        services.confirm_upi_payment(payment_id, actor=request.user, request=request)
        return Response(_decided(payment_id, salon))


class _RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True)


class OwnerRejectPaymentView(OwnerView):
    def post(self, request, payment_id):
        salon = _active_salon()
        data = _RejectSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.reject_upi_payment(
            payment_id,
            actor=request.user,
            reason=data.validated_data.get("reason", ""),
            request=request,
        )
        return Response(_decided(payment_id, salon))
