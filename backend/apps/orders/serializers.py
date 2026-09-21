"""Order API serialization.

The request serializers accept ONLY service ids, quantities and contact fields.
There is deliberately no price, total or status field to bind: an attacker
sending one gets it ignored rather than validated, because the field does not
exist here at all.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.orders.services import MAX_QUANTITY_PER_SERVICE


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


def serialize_order(order) -> dict:
    """The customer-facing order payload.

    Note what is absent: the customer's full phone number, the campaign config
    id, the internal salon id and anything about the lucky campaign. The phone
    is echoed masked so the customer can confirm they typed it right without
    the number being readable from a shared screen or a cached response.
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
    }
