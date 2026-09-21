"""The cron endpoint must be unreachable without the shared secret.

It closes campaigns and expires reservations, so an unauthenticated caller
must not be able to trigger it -- and a missing secret must lock everyone out
rather than let an empty header match an empty secret.
"""

from __future__ import annotations

from unittest import mock

import pytest

URL = "/api/v1/internal/cron/daily-rollover"
SECRET = "s" * 40


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", SECRET)
    return SECRET


def _patched():
    return (
        mock.patch(
            "tasks.campaigns.close_and_open_daily_campaign", return_value={"closed": 1, "opened": 1}
        ),
        mock.patch("tasks.campaigns.expire_stale_reservations", return_value=3),
    )


def test_no_header_is_refused(client, secret):
    assert client.get(URL).status_code == 401


def test_wrong_secret_is_refused(client, secret):
    r = client.get(URL, HTTP_AUTHORIZATION="Bearer " + "x" * 40)
    assert r.status_code == 401


def test_secret_without_bearer_prefix_is_refused(client, secret):
    assert client.get(URL, HTTP_AUTHORIZATION=SECRET).status_code == 401


def test_missing_secret_locks_everyone_out(client, monkeypatch):
    """Fail closed: no configured secret must not mean 'no check'."""
    monkeypatch.delenv("CRON_SECRET", raising=False)
    assert client.get(URL, HTTP_AUTHORIZATION="Bearer ").status_code == 401
    assert client.get(URL).status_code == 401


def test_short_secret_is_treated_as_misconfiguration(client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "short")
    assert client.get(URL, HTTP_AUTHORIZATION="Bearer short").status_code == 401


def test_correct_secret_runs_the_rollover(client, secret):
    rollover, expire = _patched()
    with rollover as r, expire as e:
        resp = client.get(URL, HTTP_AUTHORIZATION=f"Bearer {secret}")
    assert resp.status_code == 200
    assert resp.json() == {"closed": 1, "opened": 1, "reservations_expired": 3}
    r.assert_called_once()
    e.assert_called_once()


def test_post_is_not_allowed(client, secret):
    assert client.post(URL, HTTP_AUTHORIZATION=f"Bearer {secret}").status_code == 405


@pytest.mark.django_db
def test_real_rollover_provisions_today(client, secret):
    """End to end against the real task code: a salon with a config gets
    today's campaign."""
    import datetime as dt

    from apps.promotions.models import CampaignConfig, DailyCampaign
    from apps.salons.models import Salon

    salon = Salon.objects.create(name="S", slug="s")
    CampaignConfig.objects.create(
        salon=salon, daily_capacity=40, lucky_count=5, effective_from=dt.date(2000, 1, 1)
    )
    resp = client.get(URL, HTTP_AUTHORIZATION=f"Bearer {secret}")
    assert resp.status_code == 200
    assert resp.json()["opened"] == 1
    assert DailyCampaign.objects.count() == 1
