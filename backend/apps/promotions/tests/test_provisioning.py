"""Daily campaign creation, locking and the public payload."""

from __future__ import annotations

import datetime as dt
import json
import threading

import pytest
from django.db import connections

from apps.promotions.lucky import verify_commitment, winning_positions
from apps.promotions.models import CampaignStatus, DailyCampaign
from apps.promotions.services import (
    CampaignNotConfigured,
    close_campaign,
    decrypt_winning_positions,
    provision_campaign,
    public_progress,
)
from common.crypto import decrypt

pytestmark = pytest.mark.django_db


def test_provisioning_creates_one_campaign_for_today(salon, config):
    campaign = provision_campaign(salon)

    assert campaign.status == CampaignStatus.ACTIVE
    assert campaign.capacity == 40
    assert campaign.lucky_count == 5
    assert campaign.paid_count == 0
    assert DailyCampaign.objects.count() == 1


def test_provisioning_is_idempotent(salon, config):
    first = provision_campaign(salon)
    second = provision_campaign(salon)

    assert first.id == second.id
    assert DailyCampaign.objects.count() == 1


def test_settings_are_snapshotted_not_referenced(salon, config):
    """A later config change must not rewrite a day that has already run."""
    campaign = provision_campaign(salon)

    config.daily_capacity = 100
    config.discount_percent = 25
    config.save()

    campaign.refresh_from_db()
    assert campaign.capacity == 40
    assert campaign.discount_percent == 10


def test_seed_and_positions_are_encrypted_at_rest(salon, config):
    campaign = provision_campaign(salon)

    # Fernet tokens, not plaintext.
    assert campaign.encrypted_seed.startswith("gAAAAA")
    assert campaign.encrypted_winning_positions.startswith("gAAAAA")

    # The serialised list must not appear in the ciphertext. Checking each
    # position individually would be meaningless: "2" occurs in base64 by
    # chance, so such a test passes or fails at random.
    positions = decrypt_winning_positions(campaign)
    assert json.dumps(positions) not in campaign.encrypted_winning_positions
    assert str(positions) not in campaign.encrypted_winning_positions

    # And the ciphertext is genuinely reversible only with the key.
    assert json.loads(decrypt(campaign.encrypted_winning_positions)) == positions


def test_stored_positions_match_the_stored_seed(salon, config):
    """The audit chain: seed -> positions must reproduce what was stored."""
    campaign = provision_campaign(salon)
    seed = decrypt(campaign.encrypted_seed)

    assert decrypt_winning_positions(campaign) == winning_positions(
        seed, campaign.capacity, campaign.lucky_count
    )


def test_commitment_verifies_against_the_stored_seed(salon, config):
    """What proves, after the day is over, that the draw predated play."""
    campaign = provision_campaign(salon)
    seed = decrypt(campaign.encrypted_seed)

    assert verify_commitment(
        seed,
        campaign.seed_commitment,
        salon_id=salon.id,
        campaign_date=campaign.campaign_date,
        capacity=campaign.capacity,
        lucky_count=campaign.lucky_count,
    )


def test_exactly_lucky_count_positions_are_drawn(salon, config):
    campaign = provision_campaign(salon)
    positions = decrypt_winning_positions(campaign)

    assert len(positions) == 5
    assert len(set(positions)) == 5
    assert all(1 <= p <= 40 for p in positions)


def test_missing_config_refuses_to_provision(salon):
    with pytest.raises(CampaignNotConfigured):
        provision_campaign(salon)


def test_each_date_gets_its_own_campaign(salon, config):
    a = provision_campaign(salon, dt.date(2026, 9, 21))
    b = provision_campaign(salon, dt.date(2026, 9, 22))

    assert a.id != b.id
    assert a.seed_commitment != b.seed_commitment
    assert DailyCampaign.objects.count() == 2


def test_yesterday_is_never_reset(salon, config):
    yesterday = provision_campaign(salon, dt.date(2026, 9, 20))
    close_campaign(yesterday)
    original_commitment = yesterday.seed_commitment

    provision_campaign(salon, dt.date(2026, 9, 21))

    yesterday.refresh_from_db()
    assert yesterday.status == CampaignStatus.CLOSED
    assert yesterday.seed_commitment == original_commitment


# --- config lock ----------------------------------------------------------


def test_campaign_is_unlocked_before_anyone_pays(salon, config):
    assert provision_campaign(salon).is_locked is False


def test_campaign_locks_once_someone_has_paid(salon, config):
    campaign = provision_campaign(salon)
    DailyCampaign.objects.filter(pk=campaign.pk).update(paid_count=1)
    campaign.refresh_from_db()

    assert campaign.is_locked is True


# --- provisioning race ----------------------------------------------------


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_scheduler_and_lazy_path_racing_produce_one_campaign(salon, config):
    """The Beat task and a customer's first request will collide at midnight.

    UNIQUE (salon, campaign_date) is what makes that safe: one INSERT wins, the
    others re-read.
    """
    threads = 12
    barrier = threading.Barrier(threads)
    ids: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def attempt():
        try:
            barrier.wait(timeout=20)
            campaign = provision_campaign(salon)
            with lock:
                ids.append(str(campaign.id))
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
    assert len(set(ids)) == 1, "all callers must see the same campaign"
    assert DailyCampaign.objects.count() == 1


# --- public payload -------------------------------------------------------


def test_public_progress_exposes_only_safe_counters(salon, config):
    """Doc 1 section 16. The assertion is on the exact key set, so adding a
    field to the payload fails here until someone has thought about it."""
    campaign = provision_campaign(salon)
    payload = public_progress(campaign)

    assert set(payload) == {
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


def test_public_progress_leaks_no_secret(salon, config):
    campaign = provision_campaign(salon)
    positions = decrypt_winning_positions(campaign)
    blob = json.dumps(public_progress(campaign))

    assert campaign.encrypted_seed not in blob
    assert campaign.seed_commitment not in blob
    for key in ("seed", "position", "winning", "encrypted"):
        assert key not in blob.lower()
    # And the positions themselves must not be inferable from the payload.
    assert str(positions) not in blob


def test_progress_counters_are_consistent(salon, config):
    campaign = provision_campaign(salon)
    DailyCampaign.objects.filter(pk=campaign.pk).update(paid_count=28, winner_count=3)
    campaign.refresh_from_db()

    payload = public_progress(campaign)
    assert payload["paid_count"] == 28
    assert payload["slots_remaining"] == 12
    assert payload["winners_found"] == 3
    assert payload["winners_remaining"] == 2
    assert payload["is_open"] is True


def test_progress_reports_closed_when_full(salon, config):
    campaign = provision_campaign(salon)
    DailyCampaign.objects.filter(pk=campaign.pk).update(paid_count=40)
    campaign.refresh_from_db()

    payload = public_progress(campaign)
    assert payload["slots_remaining"] == 0
    assert payload["is_open"] is False
