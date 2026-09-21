from __future__ import annotations

from rest_framework import serializers
from rest_framework.response import Response

from apps.accounts.views import OwnerView
from apps.refunds import services
from apps.refunds.models import Refund, RefundMethod, RefundStatus
from apps.salons.models import Salon
from common.exceptions import NotFound, ValidationFailed


def _iso(value) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _active_salon() -> Salon:
    salon = Salon.objects.filter(status=Salon.Status.ACTIVE).first()
    if salon is None:
        raise NotFound("Salon is not available.")
    return salon


def serialize_refund(refund: Refund) -> dict:
    order = refund.order
    decision = getattr(order, "lucky_decision", None)
    return {
        "id": str(refund.id),
        "status": refund.status.lower(),
        "amount_paise": refund.amount_paise,
        "reason": refund.reason,
        "created_at": _iso(refund.created_at),
        "method": refund.method or None,
        "reference": refund.reference or None,
        "sent_at": _iso(refund.sent_at),
        "order": {
            "id": str(order.id),
            "public_order_number": order.public_order_number,
            "total_paise": order.total_paise,
        },
        "customer": {"name": order.customer.name, "phone": order.customer.phone},
        # The customer's own UPI reference: most UPI apps can pay a sender
        # back straight from that transaction.
        "payment_reference": refund.payment.reference if refund.payment else None,
        "participant_number": decision.participant_number if decision else None,
        "free_services": list(decision.free_services) if decision else [],
    }


_STATUS = {"pending": RefundStatus.PENDING, "sent": RefundStatus.SENT}


def _refunds():
    return Refund.objects.select_related("order__customer", "order__lucky_decision", "payment")


class OwnerRefundsView(OwnerView):
    """GET /owner/refunds?status=pending|sent"""

    def get(self, request):
        key = request.query_params.get("status", "pending")
        if key not in _STATUS:
            raise ValidationFailed("status must be pending or sent.")
        refunds = _refunds().filter(salon=_active_salon(), status=_STATUS[key])
        return Response({"results": [serialize_refund(r) for r in refunds[:100]]})


class _MarkSentSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=RefundMethod.values)
    reference = serializers.CharField(max_length=40, required=False, allow_blank=True)


class OwnerMarkRefundSentView(OwnerView):
    def post(self, request, refund_id):
        data = _MarkSentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.mark_refund_sent(
            refund_id,
            method=data.validated_data["method"],
            reference=data.validated_data.get("reference", ""),
            actor=request.user,
            request=request,
        )
        return Response(serialize_refund(_refunds().get(pk=refund_id)))
