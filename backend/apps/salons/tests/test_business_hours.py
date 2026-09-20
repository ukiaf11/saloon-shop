"""The seven-day guarantee.

`business_hours` is the one part of the salon payload the frontend renders as a
fixed table, so it must always carry exactly seven entries, Monday first, with
no times on a closed day (API_CONTRACT_PHASE2.md).
"""

from __future__ import annotations

from datetime import time

import pytest

from apps.salons.models import BusinessHour
from apps.salons.serializers import BusinessHourSerializer, week_for
from apps.salons.views import build_salon_payload

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def _by_day(payload: dict) -> dict[int, dict]:
    return {hour["day_of_week"]: hour for hour in payload["business_hours"]}


@pytest.mark.django_db
def test_salon_with_no_rows_still_reports_a_full_week(salon):
    hours = build_salon_payload()["business_hours"]

    assert [hour["day_of_week"] for hour in hours] == list(range(7))
    assert [hour["day_name"] for hour in hours] == WEEKDAY_NAMES
    assert all(hour["is_closed"] for hour in hours)
    assert all(hour["open_time"] is None and hour["close_time"] is None for hour in hours)


@pytest.mark.django_db
def test_missing_days_are_filled_around_the_stored_ones(salon):
    BusinessHour.objects.create(
        salon=salon, day_of_week=0, open_time=time(10, 0), close_time=time(21, 0)
    )
    BusinessHour.objects.create(
        salon=salon, day_of_week=2, open_time=time(11, 30), close_time=time(20, 15)
    )

    hours = _by_day(build_salon_payload())

    assert len(hours) == 7
    assert hours[0] == {
        "day_of_week": 0,
        "day_name": "Monday",
        "open_time": "10:00",
        "close_time": "21:00",
        "is_closed": False,
    }
    assert hours[2]["open_time"] == "11:30"
    assert hours[2]["close_time"] == "20:15"
    for day in (1, 3, 4, 5, 6):
        assert hours[day]["is_closed"] is True
        assert hours[day]["open_time"] is None
        assert hours[day]["close_time"] is None


@pytest.mark.django_db
def test_closed_day_reports_no_times_even_when_the_row_has_them(salon):
    BusinessHour.objects.create(
        salon=salon,
        day_of_week=6,
        open_time=time(10, 0),
        close_time=time(21, 0),
        is_closed=True,
    )

    sunday = _by_day(build_salon_payload())[6]

    assert sunday["is_closed"] is True
    assert sunday["open_time"] is None
    assert sunday["close_time"] is None


@pytest.mark.django_db
def test_days_are_ordered_monday_first_whatever_the_insert_order(salon):
    for day in (5, 0, 3):
        BusinessHour.objects.create(
            salon=salon, day_of_week=day, open_time=time(9, 0), close_time=time(18, 0)
        )

    hours = build_salon_payload()["business_hours"]

    assert [hour["day_of_week"] for hour in hours] == list(range(7))


@pytest.mark.django_db
def test_times_render_as_hh_mm_without_seconds(salon):
    BusinessHour.objects.create(
        salon=salon, day_of_week=1, open_time=time(9, 5, 30), close_time=time(18, 45, 59)
    )

    tuesday = _by_day(build_salon_payload())[1]

    assert tuesday["open_time"] == "09:05"
    assert tuesday["close_time"] == "18:45"


@pytest.mark.django_db
def test_synthesised_days_are_not_persisted(salon):
    week_for(salon)

    assert BusinessHour.objects.filter(salon=salon).count() == 0


@pytest.mark.django_db
def test_real_and_synthesised_days_share_one_shape(salon):
    BusinessHour.objects.create(
        salon=salon, day_of_week=4, open_time=time(10, 0), close_time=time(22, 0)
    )

    serialized = BusinessHourSerializer(week_for(salon), many=True).data
    shapes = {tuple(sorted(entry)) for entry in serialized}

    assert len(shapes) == 1
