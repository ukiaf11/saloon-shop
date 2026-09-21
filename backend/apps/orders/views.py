from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.serializers import (
    OrderCreateRequestSerializer,
    QuoteRequestSerializer,
    serialize_order,
    serialize_quote,
)
from apps.orders.services import build_quote, create_order
from apps.salons.models import Salon
from common.exceptions import NotFound

IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"
MAX_IDEMPOTENCY_KEY_LENGTH = 128


def _active_salon() -> Salon:
    salon = Salon.objects.filter(status=Salon.Status.ACTIVE).first()
    if salon is None:
        raise NotFound("Salon is not available.")
    return salon


class QuoteView(APIView):
    """POST /orders/quote -- advisory pricing. Writes nothing."""

    permission_classes = (AllowAny,)
    throttle_scope = "quote"

    def post(self, request):
        serializer = QuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quote = build_quote(_active_salon(), serializer.validated_data["items"])
        return Response(serialize_quote(quote))


class OrderCreateView(APIView):
    """POST /orders -- creates the order and snapshots its prices."""

    permission_classes = (AllowAny,)
    throttle_scope = "order_create"

    def post(self, request):
        serializer = OrderCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        customer = data["customer"]

        # Truncated rather than rejected: an over-long key is a client bug, and
        # failing the checkout over it would cost a sale for nothing.
        idempotency_key = (request.META.get(IDEMPOTENCY_HEADER, "") or "").strip()[
            :MAX_IDEMPOTENCY_KEY_LENGTH
        ] or None

        order = create_order(
            _active_salon(),
            data["items"],
            customer_name=customer["name"],
            customer_phone=customer["phone"],
            customer_email=customer.get("email", ""),
            idempotency_key=idempotency_key,
        )
        return Response(serialize_order(order), status=201)


def order_for_display(order_id) -> Order | None:
    """An order with everything serialize_order reads, in a fixed few queries."""
    return (
        Order.objects.select_related(
            "customer",
            "lucky_decision__daily_campaign",
            "slot_reservation__daily_campaign",
        )
        .prefetch_related("items", "payments", "refunds")
        .filter(id=order_id)
        .first()
    )


class OrderDetailView(APIView):
    """GET /orders/{id} -- recovery for a client that lost its response.

    Guarded only by the unguessability of the UUID, which is why the payload
    carries no full phone number and no internal identifiers.
    """

    permission_classes = (AllowAny,)
    throttle_scope = "public_read"

    def get(self, request, order_id):
        order = order_for_display(order_id)
        if order is None:
            raise NotFound("Order not found.")
        return Response(serialize_order(order))
