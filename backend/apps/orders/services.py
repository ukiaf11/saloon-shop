"""Quote and order creation.

The one rule that governs this module: the client supplies service ids,
quantities and contact details. Everything financial is computed here, from the
catalogue, every time. A price in a request body is not rejected -- it is simply
never read.

Order creation recomputes rather than trusting the quote it was shown, because a
quote is a UI convenience and the catalogue can change between the two calls.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalog.models import Service
from apps.customers.services import get_or_create_customer
from apps.orders.models import Order, OrderItem, generate_public_order_number
from apps.promotions.models import CampaignConfig
from apps.promotions.services import config_for, salon_today
from apps.salons.models import Salon
from common.exceptions import ValidationFailed
from common.money import Paise, allocate_discount, percent_of

logger = logging.getLogger(__name__)

MAX_DISTINCT_SERVICES = 20
MAX_QUANTITY_PER_SERVICE = 10
QUOTE_TTL_SECONDS = 300


class ServiceUnavailable(ValidationFailed):
    code = "service_unavailable_for_order"
    message = "One or more selected services are no longer available."


@dataclass(frozen=True)
class RequestedItem:
    service_id: str
    quantity: int


@dataclass(frozen=True)
class QuoteLine:
    service: Service
    quantity: int
    unit_price_paise: Paise
    line_total_paise: Paise
    discount_alloc_paise: Paise
    net_paid_paise: Paise


@dataclass(frozen=True)
class Quote:
    lines: tuple[QuoteLine, ...]
    subtotal_paise: Paise
    #: The rate actually applied -- 0 when the basket is not eligible, so the
    #: UI can never show a discount that was not given.
    discount_percent: int
    #: The rate configured for the campaign, whether or not it applied. Lets
    #: the UI say "add 1 more service to unlock 10% off" without implying the
    #: discount is already on the total.
    configured_discount_percent: int
    discount_paise: Paise
    payable_paise: Paise
    eligible_for_discount: bool
    distinct_service_count: int
    min_distinct_services: int
    config: CampaignConfig
    expires_at: dt.datetime


def normalise_items(raw_items: list[dict]) -> list[RequestedItem]:
    """Validate and merge the requested items.

    Duplicate service ids are merged by summing quantity rather than rejected:
    a UI that adds the same service twice means quantity 2, and failing the
    request would be a worse answer than the obvious one.
    """
    if not raw_items:
        raise ValidationFailed("Select at least one service.")

    merged: dict[str, int] = {}
    for entry in raw_items:
        service_id = str(entry.get("service_id") or "").strip()
        if not service_id:
            raise ValidationFailed("Each item needs a service_id.")

        quantity = entry.get("quantity", 1)
        if quantity is None:
            quantity = 1
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise ValidationFailed("Quantity must be a whole number.")
        if not 1 <= quantity <= MAX_QUANTITY_PER_SERVICE:
            raise ValidationFailed(f"Quantity must be between 1 and {MAX_QUANTITY_PER_SERVICE}.")

        merged[service_id] = merged.get(service_id, 0) + quantity

    if len(merged) > MAX_DISTINCT_SERVICES:
        raise ValidationFailed(f"Select at most {MAX_DISTINCT_SERVICES} different services.")

    for quantity in merged.values():
        if quantity > MAX_QUANTITY_PER_SERVICE:
            raise ValidationFailed(f"Quantity must be between 1 and {MAX_QUANTITY_PER_SERVICE}.")

    return [RequestedItem(service_id=k, quantity=v) for k, v in merged.items()]


def _load_services(salon: Salon, items: list[RequestedItem]) -> dict[str, Service]:
    """Fetch the active services, refusing the whole basket if any is missing.

    Partial fulfilment is deliberately not offered: silently dropping a service
    the customer chose would charge them for a basket they did not assemble.
    """
    ids = [item.service_id for item in items]
    try:
        found = {
            str(s.id): s
            for s in Service.objects.select_related("category").filter(
                salon=salon, id__in=ids, is_active=True
            )
        }
    except (ValueError, TypeError) as exc:
        # A malformed uuid reaches the ORM as a cast error.
        raise ValidationFailed("One or more service ids are not valid.") from exc

    missing = [i for i in ids if i not in found]
    if missing:
        raise ServiceUnavailable(context={"unavailable_service_ids": missing})
    return found


def build_quote(
    salon: Salon,
    raw_items: list[dict],
    *,
    on_date: dt.date | None = None,
) -> Quote:
    """Price a basket. Pure read -- writes nothing."""
    items = normalise_items(raw_items)
    services = _load_services(salon, items)
    config = config_for(salon, on_date or salon_today(salon))

    # Distinct *services*, not units. Buying three haircuts is one service and
    # must not unlock the multi-service discount (Doc 1 section 3.2).
    distinct_service_count = len(items)
    eligible = distinct_service_count >= config.min_distinct_services

    priced: list[tuple[str, Paise, Service, int]] = []
    for item in items:
        service = services[item.service_id]
        unit = service.price_paise
        priced.append((str(service.id), unit * item.quantity, service, item.quantity))

    subtotal_paise = sum(line_total for _, line_total, _, _ in priced)

    discount_percent = config.discount_percent if eligible else 0
    discount_paise = percent_of(subtotal_paise, discount_percent) if eligible else 0

    allocation = allocate_discount(
        [(key, line_total) for key, line_total, _, _ in priced], discount_paise
    )

    lines = tuple(
        QuoteLine(
            service=service,
            quantity=quantity,
            unit_price_paise=service.price_paise,
            line_total_paise=line_total,
            discount_alloc_paise=allocation.by_key(key).discount_alloc_paise,
            net_paid_paise=allocation.by_key(key).net_paid_paise,
        )
        for key, line_total, service, quantity in priced
    )

    payable_paise = subtotal_paise - discount_paise

    # Cheap assertions over an expensive class of bug: these three sums are what
    # a winner's partial refund is later computed from.
    assert sum(line.line_total_paise for line in lines) == subtotal_paise
    assert sum(line.discount_alloc_paise for line in lines) == discount_paise
    assert sum(line.net_paid_paise for line in lines) == payable_paise

    return Quote(
        lines=lines,
        subtotal_paise=subtotal_paise,
        discount_percent=discount_percent,
        configured_discount_percent=config.discount_percent,
        discount_paise=discount_paise,
        payable_paise=payable_paise,
        eligible_for_discount=eligible,
        distinct_service_count=distinct_service_count,
        min_distinct_services=config.min_distinct_services,
        config=config,
        expires_at=timezone.now() + dt.timedelta(seconds=QUOTE_TTL_SECONDS),
    )


@transaction.atomic
def create_order(
    salon: Salon,
    raw_items: list[dict],
    *,
    customer_name: str,
    customer_phone: str,
    customer_email: str = "",
    idempotency_key: str | None = None,
) -> Order:
    """Create an order with snapshotted prices.

    Recomputes the quote rather than accepting one from the client. If the
    catalogue changed since the customer saw their total, the order is created
    at the current price and the payment step shows it -- the alternative is
    honouring a price the salon no longer offers.
    """
    if idempotency_key:
        existing = Order.objects.filter(salon=salon, idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

    quote = build_quote(salon, raw_items)
    customer = get_or_create_customer(
        name=customer_name, phone=customer_phone, email=customer_email
    )

    order = Order(
        salon=salon,
        customer=customer,
        campaign_config=quote.config,
        public_order_number=_unique_order_number(salon),
        subtotal_paise=quote.subtotal_paise,
        discount_paise=quote.discount_paise,
        total_paise=quote.payable_paise,
        discount_percent_applied=quote.discount_percent,
        idempotency_key=idempotency_key or None,
    )

    try:
        order.save()
    except IntegrityError:
        # Two concurrent submits of the same form: the loser finds the winner's
        # order rather than creating a duplicate.
        if idempotency_key:
            existing = Order.objects.filter(salon=salon, idempotency_key=idempotency_key).first()
            if existing is not None:
                return existing
        raise

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                service=line.service,
                service_name_snapshot=line.service.name,
                service_slug_snapshot=line.service.slug,
                unit_price_paise=line.unit_price_paise,
                quantity=line.quantity,
                line_total_paise=line.line_total_paise,
                discount_alloc_paise=line.discount_alloc_paise,
                net_paid_paise=line.net_paid_paise,
            )
            for line in quote.lines
        ]
    )

    logger.info(
        "order_created",
        extra={
            "order_id": str(order.id),
            "public_order_number": order.public_order_number,
            "subtotal_paise": order.subtotal_paise,
            "discount_paise": order.discount_paise,
            "total_paise": order.total_paise,
            "distinct_services": quote.distinct_service_count,
            "discount_applied": quote.eligible_for_discount,
        },
    )
    return order


def _unique_order_number(salon: Salon, attempts: int = 8) -> str:
    """A free public order number.

    The suffix is 4 chars from a 32-symbol alphabet, so collisions are rare but
    not impossible; retrying beats letting a unique-constraint error surface as
    a failed checkout.
    """
    today = salon_today(salon)
    for _ in range(attempts):
        candidate = generate_public_order_number(today)
        if not Order.objects.filter(public_order_number=candidate).exists():
            return candidate
    raise RuntimeError("Could not allocate a unique public order number.")
