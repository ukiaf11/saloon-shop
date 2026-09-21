"""Capacity admission under concurrency.

Doc 3 section 47 names this the critical test: with one slot left and twenty
simultaneous checkouts, exactly one may be admitted. These run real threads
against real Postgres, because the whole mechanism is a row lock -- a mocked
database would prove nothing.
"""

from __future__ import annotations

import datetime as dt
import threading

import pytest
from django.db import connections
from django.utils import timezone

from apps.promotions.models import (
    CampaignStatus,
    DailyCampaign,
    ReservationStatus,
    SlotReservation,
)
from apps.promotions.services import (
    CampaignClosed,
    CapacityExhausted,
    close_campaign,
    expire_stale_reservations,
    provision_campaign,
    reserve_slot,
)

pytestmark = pytest.mark.django_db


def test_reservation_is_taken_and_counted(salon, config):
    campaign = provision_campaign(salon)
    reservation = reserve_slot(campaign)

    assert reservation.status == ReservationStatus.ACTIVE
    assert reservation.is_live
    assert SlotReservation.objects.filter(daily_campaign=campaign).count() == 1


def test_capacity_counts_paid_plus_live_holds(salon, config):
    """Holds must count. Otherwise the last slot is promised to everyone who is
    still paying for it."""
    campaign = provision_campaign(salon)
    # lucky_count must come down with capacity: the DB enforces
    # lucky_count <= capacity, and rightly so.
    DailyCampaign.objects.filter(pk=campaign.pk).update(capacity=3, lucky_count=1, paid_count=1)
    campaign.refresh_from_db()

    reserve_slot(campaign)
    reserve_slot(campaign)

    with pytest.raises(CapacityExhausted):
        reserve_slot(campaign)


def test_expired_holds_free_their_slot(salon, config):
    campaign = provision_campaign(salon)
    DailyCampaign.objects.filter(pk=campaign.pk).update(capacity=1, lucky_count=1)
    campaign.refresh_from_db()

    reserve_slot(campaign, ttl_seconds=1)
    with pytest.raises(CapacityExhausted):
        reserve_slot(campaign)

    SlotReservation.objects.update(expires_at=timezone.now() - dt.timedelta(seconds=1))
    freed = expire_stale_reservations()
    assert freed == 1

    assert reserve_slot(campaign).status == ReservationStatus.ACTIVE


def test_a_closed_campaign_refuses_reservations(salon, config):
    campaign = provision_campaign(salon)
    close_campaign(campaign)

    with pytest.raises(CampaignClosed):
        reserve_slot(campaign)


def test_closing_expires_outstanding_holds(salon, config):
    campaign = provision_campaign(salon)
    reserve_slot(campaign)

    close_campaign(campaign)

    assert SlotReservation.objects.filter(status=ReservationStatus.ACTIVE).count() == 0
    campaign.refresh_from_db()
    assert campaign.status == CampaignStatus.CLOSED
    assert campaign.closed_at is not None


def test_closing_twice_is_harmless(salon, config):
    campaign = provision_campaign(salon)
    first = close_campaign(campaign)
    second = close_campaign(campaign)
    assert first.closed_at == second.closed_at


# --- the exit gate --------------------------------------------------------


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_twenty_simultaneous_checkouts_for_the_last_slot(salon, config):
    """capacity=40, paid=39, 20 threads race. Exactly one may win.

    transaction=True is required: each thread needs its own real connection, so
    the row lock is actually exercised instead of being trivially satisfied
    inside one shared transaction.
    """
    campaign = provision_campaign(salon)
    DailyCampaign.objects.filter(pk=campaign.pk).update(capacity=40, paid_count=39)
    campaign.refresh_from_db()

    threads = 20
    barrier = threading.Barrier(threads)
    admitted: list[str] = []
    refused: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def attempt():
        try:
            barrier.wait(timeout=20)  # release all threads at the same instant
            reservation = reserve_slot(campaign)
            with lock:
                admitted.append(str(reservation.id))
        except CapacityExhausted:
            with lock:
                refused.append("full")
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            connections.close_all()

    workers = [threading.Thread(target=attempt) for _ in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=30)

    assert not errors, f"unexpected errors: {errors[:3]}"
    assert len(admitted) == 1, f"expected exactly 1 admitted, got {len(admitted)}"
    assert len(refused) == threads - 1

    campaign.refresh_from_db()
    live = SlotReservation.objects.filter(
        daily_campaign=campaign, status=ReservationStatus.ACTIVE
    ).count()
    assert campaign.paid_count + live <= campaign.capacity, "capacity was oversold"


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_concurrent_reservations_never_exceed_capacity(salon, config):
    """A wider race: 30 threads against 10 free slots."""
    campaign = provision_campaign(salon)
    DailyCampaign.objects.filter(pk=campaign.pk).update(capacity=10, lucky_count=5, paid_count=0)
    campaign.refresh_from_db()

    threads = 30
    barrier = threading.Barrier(threads)
    admitted: list[str] = []
    lock = threading.Lock()

    def attempt():
        try:
            barrier.wait(timeout=20)
            reservation = reserve_slot(campaign)
            with lock:
                admitted.append(str(reservation.id))
        except CapacityExhausted:
            pass
        finally:
            connections.close_all()

    workers = [threading.Thread(target=attempt) for _ in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=30)

    assert len(admitted) == 10, f"expected exactly 10, got {len(admitted)}"
    assert (
        SlotReservation.objects.filter(
            daily_campaign=campaign, status=ReservationStatus.ACTIVE
        ).count()
        == 10
    )
