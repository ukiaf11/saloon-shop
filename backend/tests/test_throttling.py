"""A Redis outage must degrade the API, not take it down."""

from __future__ import annotations

from unittest import mock

import pytest
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from common.throttling import ResilientScopedRateThrottle


class _View(APIView):
    throttle_scope = "public_read"


def test_request_is_allowed_when_the_cache_raises():
    throttle = ResilientScopedRateThrottle()
    request = APIRequestFactory().get("/")

    with mock.patch(
        "rest_framework.throttling.ScopedRateThrottle.allow_request",
        side_effect=ConnectionError("redis unreachable"),
    ):
        assert throttle.allow_request(request, _View()) is True


@pytest.mark.django_db
def test_public_endpoint_survives_a_cache_outage(client):
    """End to end: with every cache call failing, /healthz and a public API
    route must still answer rather than 500."""
    from django.core.cache import cache

    with (
        mock.patch.object(cache, "get", side_effect=ConnectionError("down")),
        mock.patch.object(cache, "set", side_effect=ConnectionError("down")),
        mock.patch.object(cache, "add", side_effect=ConnectionError("down")),
    ):
        assert client.get("/healthz").status_code == 200
        r = client.get("/api/v1/services")
        assert r.status_code != 500, "a cache outage must not 500 the public API"


def test_real_rate_limits_still_apply_when_the_cache_works():
    """Failing open must not mean never limiting."""
    throttle = ResilientScopedRateThrottle()
    request = APIRequestFactory().get("/")

    with mock.patch(
        "rest_framework.throttling.ScopedRateThrottle.allow_request",
        return_value=False,
    ):
        assert throttle.allow_request(request, _View()) is False


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        ("10/min", (10, 60)),
        ("120/m", (120, 60)),
        ("5/15min", (5, 900)),
        ("3/10min", (3, 600)),
        ("100/h", (100, 3600)),
        ("2/day", (2, 86400)),
    ],
)
def test_rates_with_a_multiplied_period_parse(rate, expected):
    """DRF alone reads "15min" as unit "1" and raises; the fail-open wrapper
    then swallowed that, leaving the scope silently unthrottled."""
    assert ResilientScopedRateThrottle().parse_rate(rate) == expected


def test_every_configured_rate_parses(settings):
    throttle = ResilientScopedRateThrottle()
    for scope, rate in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].items():
        num, duration = throttle.parse_rate(rate)
        assert num > 0 and duration > 0, scope
