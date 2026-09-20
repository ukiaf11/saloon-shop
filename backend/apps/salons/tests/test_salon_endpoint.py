"""GET /salon -- contract shape, access rules and caching."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from apps.salons.models import Salon
from apps.salons.urls import urlpatterns
from apps.salons.views import SalonView, build_salon_payload
from common.cache import KEY_SALON

CONTRACT_FIELDS = {
    "name",
    "slug",
    "timezone",
    "currency",
    "address",
    "phone",
    "whatsapp",
    "email",
    "maps_url",
    "business_hours",
    "content",
}

CONTRACT_HOUR_FIELDS = {"day_of_week", "day_name", "open_time", "close_time", "is_closed"}


def _get():
    return SalonView.as_view()(APIRequestFactory().get("/api/v1/salon"))


def test_endpoint_is_public_and_throttled_as_a_public_read():
    # The project default is IsAuthenticated, so this has to be explicit.
    assert AllowAny in SalonView.permission_classes
    assert SalonView.throttle_scope == "public_read"


def test_url_is_named_salon_without_a_version_prefix():
    route = next(entry for entry in urlpatterns if entry.name == "salon")

    assert str(route.pattern) == "salon"


@pytest.mark.django_db
def test_anonymous_request_returns_the_contract_shape(salon, no_cache):
    response = _get()

    assert response.status_code == 200
    assert set(response.data) == CONTRACT_FIELDS
    assert response.data["name"] == "Upendra Salon"
    assert response.data["slug"] == "upendra-salon"
    assert response.data["timezone"] == "Asia/Kolkata"
    assert response.data["currency"] == "INR"
    assert len(response.data["business_hours"]) == 7
    for hour in response.data["business_hours"]:
        assert set(hour) == CONTRACT_HOUR_FIELDS


@pytest.mark.django_db
def test_internal_fields_are_never_exposed(salon, no_cache):
    response = _get()

    assert "id" not in response.data
    assert "status" not in response.data


@pytest.mark.django_db
def test_missing_salon_returns_the_error_envelope(db, no_cache):
    response = _get()

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_inactive_salon_is_not_published(salon, no_cache):
    Salon.objects.filter(pk=salon.pk).update(status=Salon.Status.INACTIVE)

    assert _get().status_code == 404


@pytest.mark.django_db
def test_payload_is_served_from_the_shared_cache_key(salon, settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "salon-endpoint-test",
        }
    }
    cache.clear()

    first = _get().data
    # A write that skips invalidation must not be visible: it proves the second
    # read came out of the cache rather than the database.
    Salon.objects.filter(pk=salon.pk).update(name="Renamed Salon")
    second = _get().data

    assert cache.get(KEY_SALON)["name"] == "Upendra Salon"
    assert second["name"] == first["name"] == "Upendra Salon"


@pytest.mark.django_db
def test_blank_optional_fields_serialize_as_null_not_empty_string(salon):
    """API_CONTRACT_PHASE2.md: null means absent. An unset CharField must not
    reach the frontend as "", or every consumer has to test for both."""
    salon.address = ""
    salon.phone = ""
    salon.whatsapp = ""
    salon.email = ""
    salon.maps_url = ""
    salon.save()

    payload = build_salon_payload()

    for field in ("address", "phone", "whatsapp", "email", "maps_url"):
        assert payload[field] is None, f"{field} should be null when blank"
