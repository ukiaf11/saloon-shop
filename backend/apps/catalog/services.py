"""Catalog write paths and the public catalogue payload builder.

Every price change goes through :func:`change_service_price`. It is the only
place that may authorise ``Service.save()`` to persist a new price, because it
is the only place that writes the mandatory ``ServicePriceHistory`` row
(REQUIREMENTS.md 2.2).
"""

from __future__ import annotations

from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Service, ServiceCategory, ServicePriceHistory
from apps.catalog.serializers import ServiceCategorySerializer, ServiceSerializer
from common.cache import KEY_SERVICES, invalidate
from common.exceptions import ValidationFailed
from common.locks import lock_row
from common.money import Paise

__all__ = [
    "build_services_payload",
    "change_service_price",
    "create_service",
    "invalidate_services_cache",
    "update_service",
]


def invalidate_services_cache() -> None:
    """Drop the cached ``/services`` payload now and again after commit.

    Two deletes, because one is not enough. The immediate delete bounds
    staleness while a long transaction is still open; the post-commit delete
    closes the race where a concurrent reader repopulates the cache from the
    pre-commit row. API_CONTRACT_PHASE2.md requires a price change to be
    visible immediately, not at the TTL backstop.

    Outside a transaction ``on_commit`` runs inline, so this is safe anywhere.
    """
    invalidate(KEY_SERVICES)
    transaction.on_commit(lambda: invalidate(KEY_SERVICES))


@transaction.atomic
def change_service_price(
    service: Service,
    new_price_paise: Paise,
    changed_by=None,
    reason: str = "",
) -> Service:
    """Record and apply a price change. Returns the refreshed service.

    A no-op when the price is unchanged: an audit trail full of
    ``30000 -> 30000`` rows hides the changes that matter.

    The caller's instance is not updated in place -- use the return value.
    """
    if isinstance(new_price_paise, bool) or not isinstance(new_price_paise, int):
        raise ValidationFailed("price_paise must be an integer number of paise.")
    if new_price_paise < 0:
        raise ValidationFailed("price_paise must be non-negative.")

    # Lock the row: two concurrent edits would otherwise both read the same
    # old price and write a history pair whose sequence never happened.
    locked = lock_row(Service.objects.all(), pk=service.pk)
    old_price_paise = locked.price_paise
    if old_price_paise == new_price_paise:
        return locked

    ServicePriceHistory.objects.create(
        service=locked,
        old_price_paise=old_price_paise,
        new_price_paise=new_price_paise,
        changed_by=changed_by,
        reason=reason,
    )

    locked.price_paise = new_price_paise
    locked.mark_price_change_authorised()
    locked.save(update_fields=["price_paise", "updated_at"])

    invalidate_services_cache()
    return locked


def create_service(
    *,
    salon,
    name: str,
    price_paise: Paise,
    slug: str = "",
    **fields,
) -> Service:
    """Create a service. No history row: there is no old price to record."""
    if isinstance(price_paise, bool) or not isinstance(price_paise, int):
        raise ValidationFailed("price_paise must be an integer number of paise.")
    if price_paise < 0:
        raise ValidationFailed("price_paise must be non-negative.")

    service = Service.objects.create(
        salon=salon,
        name=name,
        slug=slug or slugify(name),
        price_paise=price_paise,
        **fields,
    )
    invalidate_services_cache()
    return service


@transaction.atomic
def update_service(
    service: Service, *, changed_by=None, price_reason: str = "", **fields
) -> Service:
    """Update a service. ``price_paise`` is routed through the audited path."""
    new_price_paise = fields.pop("price_paise", None)

    if fields:
        for field, value in fields.items():
            setattr(service, field, value)
        service.save(update_fields=[*fields, "updated_at"])

    if new_price_paise is not None:
        service = change_service_price(
            service, new_price_paise, changed_by=changed_by, reason=price_reason
        )

    invalidate_services_cache()
    return service


def build_services_payload() -> dict:
    """Build the ``GET /services`` payload (API_CONTRACT_PHASE2.md).

    Active rows only, ordered by display_order then name, never paginated.
    Image URLs are storage-relative here; the view makes them absolute.
    """
    categories = ServiceCategory.objects.filter(is_active=True).order_by("display_order", "name")
    services = (
        Service.objects.filter(is_active=True)
        .select_related("category")
        .order_by("display_order", "name")
    )
    # list(): the payload is pickled into Redis, and DRF's ReturnList holds a
    # reference back to the serializer (and its queryset).
    return {
        "categories": list(ServiceCategorySerializer(categories, many=True).data),
        "results": list(ServiceSerializer(services, many=True).data),
    }
