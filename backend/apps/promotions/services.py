"""Campaign configuration reads.

`config_for` is the single way to answer "what settings governed date D". Any
code that reaches for the newest CampaignConfig row directly will silently use
tomorrow's settings on today's order.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.promotions.lucky import commitment_for, generate_seed, winning_positions
from apps.promotions.models import (
    CampaignConfig,
    CampaignStatus,
    DailyCampaign,
    ReservationStatus,
    SlotReservation,
)
from apps.salons.models import Salon
from common.crypto import decrypt, encrypt
from common.exceptions import DomainError

logger = logging.getLogger(__name__)


class CampaignNotConfigured(DomainError):
    code = "campaign_not_configured"
    message = "The daily campaign has not been configured yet."


def salon_today(salon: Salon) -> dt.date:
    """Today's date in the salon's timezone, not the server's.

    A booking at 00:30 IST belongs to the new Indian day even though UTC still
    says yesterday, so the campaign date must never be read off a UTC clock.
    """
    try:
        tz = ZoneInfo(salon.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        # A malformed timezone on the salon row must not break checkout, but it
        # would silently shift the campaign date, so it is worth a log line.
        logger.error(
            "invalid_salon_timezone",
            extra={"salon_id": str(salon.pk), "timezone": salon.timezone},
        )
        tz = dt.UTC
    return timezone.now().astimezone(tz).date()


def config_for(salon: Salon, on_date: dt.date | None = None) -> CampaignConfig:
    """The configuration in force for `on_date` (default: today, salon-local).

    Raises rather than inventing defaults: guessing a discount percent would
    mean charging a customer a number nobody configured.
    """
    on_date = on_date or salon_today(salon)
    config = (
        CampaignConfig.objects.filter(salon=salon, effective_from__lte=on_date)
        .order_by("-effective_from", "-created_at")
        .first()
    )
    if config is None:
        raise CampaignNotConfigured()
    return config


# --- daily campaign provisioning -----------------------------------------


def provision_campaign(salon: Salon, on_date: dt.date | None = None) -> DailyCampaign:
    """Return today's campaign, creating it if the scheduler has not.

    Idempotent by construction: two callers racing -- the midnight Beat task and
    a customer's first request -- both end up with the same row, because
    UNIQUE (salon, campaign_date) lets exactly one INSERT win and the loser
    re-reads. Never rely on the scheduler alone (Doc 2 section 42).

    The seed is drawn here and encrypted immediately. It is the only moment the
    plaintext exists in memory.
    """
    on_date = on_date or salon_today(salon)

    existing = DailyCampaign.objects.filter(salon=salon, campaign_date=on_date).first()
    if existing is not None:
        return existing

    config = config_for(salon, on_date)
    seed = generate_seed()
    positions = winning_positions(seed, config.daily_capacity, config.lucky_count)

    try:
        with transaction.atomic():
            campaign = DailyCampaign.objects.create(
                salon=salon,
                config=config,
                campaign_date=on_date,
                capacity=config.daily_capacity,
                lucky_count=config.lucky_count,
                discount_percent=config.discount_percent,
                min_distinct_services=config.min_distinct_services,
                reward_snapshot={
                    "reward_type": config.reward_type,
                    "service_slugs": config.reward_service_slugs,
                },
                status=CampaignStatus.ACTIVE,
                seed_commitment=commitment_for(
                    seed,
                    salon_id=salon.id,
                    campaign_date=on_date,
                    capacity=config.daily_capacity,
                    lucky_count=config.lucky_count,
                ),
                encrypted_seed=encrypt(seed),
                encrypted_winning_positions=encrypt(json.dumps(positions)),
            )
    except IntegrityError:
        # Another process created it between our check and our insert. Theirs is
        # as valid as ours would have been; ours is discarded unused.
        campaign = DailyCampaign.objects.filter(salon=salon, campaign_date=on_date).first()
        if campaign is None:
            raise
        logger.info(
            "campaign_provision_race_lost",
            extra={"campaign_date": on_date.isoformat()},
        )
        return campaign

    logger.info(
        "campaign_provisioned",
        extra={
            "campaign_id": str(campaign.id),
            "campaign_date": on_date.isoformat(),
            "capacity": campaign.capacity,
            "lucky_count": campaign.lucky_count,
            # Deliberately NOT the seed or the positions.
            "seed_commitment": campaign.seed_commitment,
        },
    )
    return campaign


def decrypt_winning_positions(campaign: DailyCampaign) -> list[int]:
    """Read the drawn positions. Server-side only.

    Every caller of this function is a place a leak could happen. There is
    exactly one legitimate caller: the lucky decision made after a verified
    payment.
    """
    return json.loads(decrypt(campaign.encrypted_winning_positions).decode())


# --- capacity ------------------------------------------------------------


class CapacityExhausted(DomainError):
    code = "capacity_exhausted"
    http_status = 409
    message = "Today's promotion is full."


class CampaignClosed(DomainError):
    code = "campaign_closed"
    http_status = 409
    message = "Today's promotion has closed."


def reserve_slot(
    campaign: DailyCampaign,
    *,
    order=None,
    customer=None,
    ttl_seconds: int | None = None,
) -> SlotReservation:
    """Take a hold on one of today's slots, or raise CapacityExhausted.

    MUST be the only path to capacity. The campaign row is locked for the whole
    check-and-insert, so concurrent checkouts serialise here: exactly one of
    twenty simultaneous requests for the last slot succeeds.

    Counting `paid_count + live reservations` rather than paid alone is what
    stops the slot being promised to several people at once while they are all
    still paying.
    """
    ttl = ttl_seconds or settings.CAMPAIGN_RESERVATION_TTL_SECONDS

    with transaction.atomic():
        locked = DailyCampaign.objects.select_for_update().get(pk=campaign.pk)

        if locked.status != CampaignStatus.ACTIVE:
            raise CampaignClosed()

        now = timezone.now()
        live_holds = SlotReservation.objects.filter(
            daily_campaign=locked,
            status=ReservationStatus.ACTIVE,
            expires_at__gt=now,
        ).count()

        if locked.paid_count + live_holds >= locked.capacity:
            logger.info(
                "capacity_exhausted",
                extra={
                    "campaign_id": str(locked.id),
                    "paid_count": locked.paid_count,
                    "live_holds": live_holds,
                    "capacity": locked.capacity,
                },
            )
            raise CapacityExhausted()

        reservation = SlotReservation.objects.create(
            daily_campaign=locked,
            order=order,
            customer=customer,
            status=ReservationStatus.ACTIVE,
            expires_at=now + dt.timedelta(seconds=ttl),
        )

    return reservation


def expire_stale_reservations(now: dt.datetime | None = None) -> int:
    """Release holds whose TTL has passed. Returns how many were freed."""
    now = now or timezone.now()
    return SlotReservation.objects.filter(
        status=ReservationStatus.ACTIVE, expires_at__lte=now
    ).update(status=ReservationStatus.EXPIRED, updated_at=now)


def close_campaign(campaign: DailyCampaign) -> DailyCampaign:
    """Close a day permanently.

    Unclaimed winning positions stay unclaimed; the record is preserved exactly
    as it ended (Doc 2 section 43).
    """
    with transaction.atomic():
        locked = DailyCampaign.objects.select_for_update().get(pk=campaign.pk)
        if locked.status == CampaignStatus.CLOSED:
            return locked

        SlotReservation.objects.filter(
            daily_campaign=locked, status=ReservationStatus.ACTIVE
        ).update(status=ReservationStatus.EXPIRED)

        locked.status = CampaignStatus.CLOSED
        locked.closed_at = timezone.now()
        locked.save(update_fields=["status", "closed_at", "updated_at"])

    logger.info(
        "campaign_closed",
        extra={
            "campaign_id": str(locked.id),
            "paid_count": locked.paid_count,
            "winner_count": locked.winner_count,
        },
    )
    return locked


def public_progress(campaign: DailyCampaign) -> dict:
    """The only campaign numbers safe to expose.

    Doc 1 section 16 lists what must never appear here: future winning
    positions, the seed, customer identities, payment ids, fraud signals. This
    function is the allowlist -- add nothing to it without checking that list.
    """
    return {
        "campaign_date": campaign.campaign_date.isoformat(),
        "capacity": campaign.capacity,
        "paid_count": campaign.paid_count,
        "slots_remaining": campaign.slots_remaining,
        "lucky_count": campaign.lucky_count,
        "winners_found": campaign.winner_count,
        "winners_remaining": campaign.winners_remaining,
        "discount_percent": campaign.discount_percent,
        "min_distinct_services": campaign.min_distinct_services,
        "is_open": campaign.status == CampaignStatus.ACTIVE and campaign.slots_remaining > 0,
        "status": campaign.status,
    }
