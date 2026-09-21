from __future__ import annotations

import datetime as dt

import pytest

from apps.catalog.models import Service, ServiceCategory
from apps.promotions.models import CampaignConfig, RewardType
from apps.salons.models import Salon


@pytest.fixture
def salon(db) -> Salon:
    return Salon.objects.create(name="Test Salon", slug="test-salon")


@pytest.fixture
def config(salon) -> CampaignConfig:
    return CampaignConfig.objects.create(
        salon=salon,
        daily_capacity=40,
        lucky_count=5,
        discount_percent=10,
        min_distinct_services=2,
        reward_type=RewardType.SERVICE_PACKAGE,
        reward_definition={"service_slugs": ["hair-cutting", "shaving"]},
        effective_from=dt.date(2000, 1, 1),
    )


@pytest.fixture
def category(salon) -> ServiceCategory:
    return ServiceCategory.objects.create(salon=salon, name="Hair", slug="hair")


def _service(salon, category, name, slug, price_paise, **kwargs):
    return Service.objects.create(
        salon=salon,
        category=category,
        name=name,
        slug=slug,
        price_paise=price_paise,
        duration_minutes=30,
        **kwargs,
    )


@pytest.fixture
def haircut(salon, category) -> Service:
    return _service(salon, category, "Hair Cutting", "hair-cutting", 30000)


@pytest.fixture
def shaving(salon, category) -> Service:
    return _service(salon, category, "Shaving", "shaving", 15000)


@pytest.fixture
def hair_spa(salon, category) -> Service:
    return _service(salon, category, "Hair Spa", "hair-spa", 80000)


@pytest.fixture
def inactive_service(salon, category) -> Service:
    return _service(salon, category, "Retired", "retired", 10000, is_active=False)


@pytest.fixture
def customer_payload() -> dict:
    return {"name": "Rahul Sharma", "phone": "9000000000", "email": "r@example.com"}
