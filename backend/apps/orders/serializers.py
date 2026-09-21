"""Order API serialization.

The request serializers accept ONLY service ids, quantities and contact fields.
There is deliberately no price, total or status field to bind: an attacker
sending one gets it ignored rather than validated, because the field does not
exist here at all.
"""

from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import serializers

from apps.orders.services import MAX_QUANTITY_PER_SERVICE

#: What the API calls each payment status. The customer-facing names are part
#: of the contract; the stored enum is not.
_PAYMENT_STATUS = {
    "AWAITING_CONFIRMATION": "awaiting_confirmation",
    "CONFIRMED": "confirmed",
    "REJECTED": "rejected",
}
_PAYMENT_METHOD = {"MANUAL_UPI": "upi_qr"}


class OrderItemRequestSerializer(serializers.Serializer):
    service_id = serializers.UUIDField()
    quantity = serializers.IntegerField(
        required=False, default=1, min_value=1, max_value=MAX_QUANTITY_PER_SERVICE
    )


class QuoteRequestSerializer(serializers.Serializer):
    items = OrderItemRequestSerializer(many=True, allow_empty=False)


class CustomerRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    # Validated and normalised to E.164 by customers.services.normalise_phone;
    # a loose CharField here keeps the formatting rules in one place.
    phone = serializers.CharField(max_length=20, trim_whitespace=True)
    email = serializers.EmailField(required=False, allow_blank=True, default="")


class OrderCreateRequestSerializer(serializers.Serializer):
    items = OrderItemRequestSerializer(many=True, allow_empty=False)
    customer = CustomerRequestSerializer()


# --- responses ------------------------------------------------------------


def serialize_quote(quote) -> dict:
    return {
        "currency": "INR",
        "subtotal_paise": quote.subtotal_paise,
        "discount_percent": quote.discount_percent,
        "configured_discount_percent": quote.configured_discount_percent,
        "discount_paise": quote.discount_paise,
        "payable_paise": quote.payable_paise,
        "eligible_for_discount": quote.eligible_for_discount,
        "distinct_service_count": quote.distinct_service_count,
        "min_distinct_services": quote.min_distinct_services,
        "expires_at": quote.expires_at.isoformat().replace("+00:00", "Z"),
        "lines": [
            {
                "service_id": str(line.service.id),
                "name": line.service.name,
                "unit_price_paise": line.unit_price_paise,
                "quantity": line.quantity,
                "line_total_paise": line.line_total_paise,
                "discount_alloc_paise": line.discount_alloc_paise,
                "net_paid_paise": line.net_paid_paise,
            }
            for line in quote.lines
        ],
    }


def _iso(value) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _related(obj, name):
    """A reverse one-to-one, or None when there is no row."""
    try:
        return getattr(obj, name)
    except ObjectDoesNotExist:
        return None


def payment_block(order) -> dict:
    """The latest payment attempt, as the customer should see it.

    Only the last four digits of the UPI reference are echoed: enough for the
    customer to recognise their own entry, not enough to be useful to anyone
    reading over their shoulder.
    """
    payments = sorted(order.payments.all(), key=lambda p: p.submitted_at, reverse=True)
    latest = payments[0] if payments else None
    if latest is None:
        return {
            "status": "not_started",
            "method": None,
            "reference_last4": None,
            "rejection_reason": None,
            "submitted_at": None,
            "decided_at": None,
        }
    return {
        "status": _PAYMENT_STATUS[latest.status],
        "method": _PAYMENT_METHOD.get(latest.provider),
        "reference_last4": latest.reference[-4:],
        "rejection_reason": latest.rejection_reason or None,
        "submitted_at": _iso(latest.submitted_at),
        "decided_at": _iso(latest.decided_at),
    }


def lucky_block(order) -> dict:
    """Where this order stands in the daily draw.

    `held` means a place is kept while the payment is checked; it says nothing
    about whether that place wins, because nothing has been decided yet. The
    hidden winning positions never reach this function.
    """
    block = {
        "status": "pending",
        "reason": None,
        "participant_number": None,
        "campaign_date": None,
        "refund_paise": 0,
        "refund_status": None,
        "free_services": [],
    }

    decision = _related(order, "lucky_decision")
    if decision is not None:
        refund = next((r for r in order.refunds.all() if r.reason == "LUCKY_REWARD"), None)
        block.update(
            status="won" if decision.is_winner else "not_won",
            participant_number=decision.participant_number,
            campaign_date=decision.daily_campaign.campaign_date.isoformat(),
            refund_paise=decision.reward_refund_paise,
            refund_status=refund.status.lower() if refund else None,
            free_services=list(decision.free_services),
        )
        return block

    if order.lucky_skip_reason:
        block.update(status="not_entered", reason=order.lucky_skip_reason)
        return block

    hold = _related(order, "slot_reservation")
    if hold is not None and hold.status == "ACTIVE" and hold.expires_at > timezone.now():
        block.update(status="held", campaign_date=hold.daily_campaign.campaign_date.isoformat())
    return block


def serialize_order(order) -> dict:
    """The customer-facing order payload.

    Note what is absent: the customer's full phone number, the campaign config
    id, the internal salon id, the full UPI reference, and anything about the
    draw beyond this order's own outcome. The phone is echoed masked so the
    customer can confirm they typed it right without the number being readable
    from a shared screen or a cached response.
    """
    return {
        "id": str(order.id),
        "public_order_number": order.public_order_number,
        "status": order.status,
        "currency": "INR",
        "subtotal_paise": order.subtotal_paise,
        "discount_percent_applied": order.discount_percent_applied,
        "discount_paise": order.discount_paise,
        "total_paise": order.total_paise,
        "created_at": order.created_at.isoformat().replace("+00:00", "Z"),
        "customer": {
            "name": order.customer.name,
            "phone_masked": order.customer.masked_phone,
        },
        "items": [
            {
                "service_name": item.service_name_snapshot,
                "unit_price_paise": item.unit_price_paise,
                "quantity": item.quantity,
                "line_total_paise": item.line_total_paise,
                "discount_alloc_paise": item.discount_alloc_paise,
                "net_paid_paise": item.net_paid_paise,
            }
            for item in order.items.all()
        ],
        "paid_at": _iso(order.paid_at),
        "payment": payment_block(order),
        "lucky": lucky_block(order),
    }
