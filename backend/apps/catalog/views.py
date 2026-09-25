"""Public catalogue endpoint."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Prefetch
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.views import ManagerView
from apps.audit.services import record
from apps.catalog.models import Service, ServicePriceHistory
from apps.catalog.services import build_services_payload, change_service_price, update_service
from apps.salons.models import Salon
from common.cache import KEY_SERVICES, cached
from common.exceptions import NotFound, ValidationFailed


class ServicesView(APIView):
    """``GET /api/v1/services`` -- the whole active catalogue in one payload.

    Not paginated: the list is small, the page renders it whole, and a
    paginated envelope would break the contract the frontend validates against.
    The project default permission is IsAuthenticated, so AllowAny is set
    explicitly here rather than inherited.
    """

    permission_classes = (AllowAny,)
    throttle_scope = "public_read"

    def get(self, request):
        payload = cached(KEY_SERVICES, build_services_payload)
        return Response(_absolutise_image_urls(payload, request))


def _absolutise_image_urls(payload: dict, request) -> dict:
    """Expand storage URLs to absolute ones for this request's host.

    Done after the cache read, not before it: one cached payload serves every
    host. ``build_absolute_uri`` leaves an already-absolute URL (object
    storage, CDN) untouched.
    """
    if request is None:
        return payload
    results = [
        {**item, "image_url": request.build_absolute_uri(item["image_url"])}
        if item.get("image_url")
        else item
        for item in payload["results"]
    ]
    return {**payload, "results": results}


# --- owner/manager: the catalogue as it is managed, not as it is sold ---------

# Bounds for owner input. Wide enough for any real salon, tight enough that a
# typo (an extra zero, a paise value pasted as rupees) is caught here instead
# of on a customer's bill.
MIN_PRICE_PAISE = 100  # ₹1
MAX_PRICE_PAISE = 50_000_000  # ₹5,00,000
MIN_DURATION_MINUTES = 5
MAX_DURATION_MINUTES = 480
PRICE_HISTORY_SHOWN = 5


def _active_salon() -> Salon:
    salon = Salon.objects.filter(status=Salon.Status.ACTIVE).first()
    if salon is None:
        raise NotFound("Salon is not available.")
    return salon


def _iso(value) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def serialize_owner_service(service: Service, request) -> dict:
    """The management view of one service.

    Unlike the public payload this includes inactive rows and the recent price
    history -- and it is never cached, because the owner must see the state
    they just changed, not a snapshot.
    """
    return {
        "id": str(service.id),
        "name": service.name,
        "slug": service.slug,
        "description": service.description,
        "category": (
            {"id": str(service.category.id), "name": service.category.name}
            if service.category is not None
            else None
        ),
        "price_paise": service.price_paise,
        "duration_minutes": service.duration_minutes,
        "is_active": service.is_active,
        "is_featured": service.is_featured,
        "display_order": service.display_order,
        "image_url": (request.build_absolute_uri(service.image.url) if service.image else None),
        "updated_at": _iso(service.updated_at),
        "price_history": [
            {
                "old_price_paise": entry.old_price_paise,
                "new_price_paise": entry.new_price_paise,
                "changed_at": _iso(entry.changed_at),
                "changed_by": entry.changed_by.email if entry.changed_by else None,
                "reason": entry.reason or None,
            }
            # Sliced in Python: the queryset arrives prefetched, and a per-row
            # LIMIT query would defeat that.
            for entry in list(service.price_history.all())[:PRICE_HISTORY_SHOWN]
        ],
    }


def _owned_service(salon: Salon, service_id) -> Service:
    service = (
        Service.objects.filter(salon=salon, pk=service_id)
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "price_history",
                queryset=ServicePriceHistory.objects.select_related("changed_by"),
            )
        )
        .first()
    )
    if service is None:
        raise NotFound("Service not found.")
    return service


class OwnerServicesView(ManagerView):
    """GET /owner/services -- every service, active or not, with history."""

    def get(self, request):
        salon = _active_salon()
        services = (
            Service.objects.filter(salon=salon)
            .select_related("category")
            .prefetch_related(
                Prefetch(
                    "price_history",
                    queryset=ServicePriceHistory.objects.select_related("changed_by"),
                )
            )
            .order_by("display_order", "name")
        )
        return Response({"results": [serialize_owner_service(s, request) for s in services]})


class _PriceSerializer(serializers.Serializer):
    price_paise = serializers.IntegerField(min_value=MIN_PRICE_PAISE, max_value=MAX_PRICE_PAISE)
    reason = serializers.CharField(
        max_length=200, required=False, allow_blank=True, trim_whitespace=True
    )


class OwnerServicePriceView(ManagerView):
    """POST /owner/services/{id}/price -- the audited price change.

    Everything money-critical happens in apps.catalog.services
    .change_service_price: the row lock, the ServicePriceHistory row and the
    cache invalidation. This view only validates the input and records who.
    """

    def post(self, request, service_id):
        salon = _active_salon()
        data = _PriceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        new_price = data.validated_data["price_paise"]
        reason = data.validated_data.get("reason", "")

        service = _owned_service(salon, service_id)
        old_price = service.price_paise
        if old_price == new_price:
            # change_service_price would quietly no-op; the owner deserves to
            # know their edit changed nothing.
            raise ValidationFailed("That is already the price of this service.")

        with transaction.atomic():
            change_service_price(service, new_price, changed_by=request.user, reason=reason)
            record(
                "service.price_changed",
                actor=request.user,
                entity=service,
                before={"price_paise": old_price},
                after={"price_paise": new_price, "reason": reason or None},
                request=request,
            )
        return Response(serialize_owner_service(_owned_service(salon, service_id), request))


class _ServicePatchSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    is_featured = serializers.BooleanField(required=False)
    duration_minutes = serializers.IntegerField(
        required=False, min_value=MIN_DURATION_MINUTES, max_value=MAX_DURATION_MINUTES
    )
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=2000, trim_whitespace=True
    )


class OwnerServiceUpdateView(ManagerView):
    """PATCH /owner/services/{id} -- non-price fields.

    Price is deliberately not accepted here: it has its own endpoint so a
    client cannot slip a price change past the history-writing path.
    """

    def patch(self, request, service_id):
        salon = _active_salon()
        data = _ServicePatchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data
        if not fields:
            raise ValidationFailed("Nothing to change.")

        service = _owned_service(salon, service_id)
        before = {name: getattr(service, name) for name in fields}
        changed = {name: value for name, value in fields.items() if before[name] != value}
        if changed:
            with transaction.atomic():
                update_service(service, changed_by=request.user, **changed)
                record(
                    "service.updated",
                    actor=request.user,
                    entity=service,
                    before={name: before[name] for name in changed},
                    after=changed,
                    request=request,
                )
        return Response(serialize_owner_service(_owned_service(salon, service_id), request))
