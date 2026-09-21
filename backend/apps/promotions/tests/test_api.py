"""The public campaign endpoint, including what it must never expose."""

from __future__ import annotations

import json

import pytest

from apps.promotions.models import CampaignStatus, DailyCampaign
from apps.promotions.services import decrypt_winning_positions

pytestmark = [pytest.mark.django_db, pytest.mark.urls("apps.promotions.tests.urls")]


@pytest.fixture(autouse=True)
def _salon(salon):
    return salon


def body(response):
    return json.loads(response.content)


def test_today_provisions_lazily_when_the_scheduler_has_not_run(client, config):
    """The first visitor of the day must not meet an error because cron was late."""
    assert DailyCampaign.objects.count() == 0

    r = client.get("/promotion/today")

    assert r.status_code == 200
    assert DailyCampaign.objects.count() == 1
    assert body(r)["capacity"] == 40


def test_today_returns_the_contract_shape(client, config):
    d = body(client.get("/promotion/today"))

    assert set(d) == {
        "campaign_date",
        "capacity",
        "paid_count",
        "slots_remaining",
        "lucky_count",
        "winners_found",
        "winners_remaining",
        "discount_percent",
        "min_distinct_services",
        "is_open",
        "status",
    }


def test_today_needs_no_authentication(client, config):
    assert client.get("/promotion/today").status_code == 200


def test_response_never_carries_the_seed_or_the_positions(client, config):
    """The leak test. If this ever fails, the campaign is riggable by anyone
    who reads the response."""
    client.get("/promotion/today")
    campaign = DailyCampaign.objects.get()
    positions = decrypt_winning_positions(campaign)

    raw = client.get("/promotion/today").content.decode()

    assert campaign.encrypted_seed not in raw
    assert campaign.encrypted_winning_positions not in raw
    assert campaign.seed_commitment not in raw
    assert json.dumps(positions) not in raw
    for term in ("seed", "position", "winning", "encrypted", "commitment"):
        assert term not in raw.lower(), f"'{term}' must not appear in a public response"


def test_counters_track_the_campaign(client, config):
    client.get("/promotion/today")
    DailyCampaign.objects.update(paid_count=28, winner_count=3)

    d = body(client.get("/promotion/today"))
    assert d["paid_count"] == 28
    assert d["slots_remaining"] == 12
    assert d["winners_found"] == 3
    assert d["winners_remaining"] == 2


def test_full_campaign_reports_closed_to_new_customers(client, config):
    client.get("/promotion/today")
    DailyCampaign.objects.update(paid_count=40)

    d = body(client.get("/promotion/today"))
    assert d["slots_remaining"] == 0
    assert d["is_open"] is False


def test_closed_campaign_is_not_open(client, config):
    client.get("/promotion/today")
    DailyCampaign.objects.update(status=CampaignStatus.CLOSED)

    assert body(client.get("/promotion/today"))["is_open"] is False
