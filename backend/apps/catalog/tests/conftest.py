from __future__ import annotations

import pytest
from django.core.cache import cache

from apps.accounts.models import AdminUser, Role
from apps.catalog.models import Service, ServiceCategory
from apps.salons.models import Salon


@pytest.fixture(autouse=True)
def isolated_cache(settings):
    """Keep these tests off the shared Redis.

    The catalogue endpoint caches, so a payload left behind by a previous run
    (or by the dev server) would make an assertion pass for the wrong reason.
    Throttle counters live in the same cache, so this also stops repeated runs
    tripping the public_read rate limit.
    """
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "catalog-tests",
        }
    }
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def salon(db):
    return Salon.objects.create(name="Test Salon", slug="test-salon")


@pytest.fixture
def owner(db):
    # No password: this account only ever appears as ServicePriceHistory.changed_by.
    return AdminUser.objects.create(
        email="owner@test.local", full_name="Test Owner", role=Role.OWNER
    )


@pytest.fixture
def hair_category(salon):
    return ServiceCategory.objects.create(salon=salon, name="Hair", slug="hair", display_order=1)


@pytest.fixture
def haircut(salon, hair_category):
    return Service.objects.create(
        salon=salon,
        category=hair_category,
        name="Hair Cutting",
        slug="hair-cutting",
        description="Precision cut and styling.",
        price_paise=30000,
        duration_minutes=30,
        is_featured=True,
        display_order=1,
    )
