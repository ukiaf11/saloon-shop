from __future__ import annotations

import datetime as dt

import pytest

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
        reward_definition={"service_slugs": ["hair-cutting", "shaving", "face-massage"]},
        effective_from=dt.date(2000, 1, 1),
    )
