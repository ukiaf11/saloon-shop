"""An owner's profile edit must be visible immediately, not after the TTL."""

from __future__ import annotations

import pytest
from django.core.cache import cache

from apps.salons.models import BusinessHour, Salon
from common.cache import KEY_SALON


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_salon_save_invalidates_public_cache(salon: Salon):
    cache.set(KEY_SALON, {"name": "stale"}, 600)

    salon.address = "New address"
    salon.save()

    assert cache.get(KEY_SALON) is None


@pytest.mark.django_db
def test_business_hour_save_invalidates_public_cache(salon: Salon):
    hour = BusinessHour.objects.create(
        salon=salon, day_of_week=0, open_time="10:00", close_time="21:00"
    )
    cache.set(KEY_SALON, {"name": "stale"}, 600)

    hour.is_closed = True
    hour.save()

    assert cache.get(KEY_SALON) is None


@pytest.mark.django_db
def test_business_hour_delete_invalidates_public_cache(salon: Salon):
    hour = BusinessHour.objects.create(
        salon=salon, day_of_week=1, open_time="10:00", close_time="21:00"
    )
    cache.set(KEY_SALON, {"name": "stale"}, 600)

    hour.delete()

    assert cache.get(KEY_SALON) is None
