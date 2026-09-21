"""Daily campaign lifecycle.

The midnight task is a convenience, never a guarantee: `provision_campaign` is
also called lazily by the first campaign-dependent request, and both paths are
idempotent against UNIQUE (salon, campaign_date). A scheduler outage therefore
delays nothing (Doc 2 section 42).
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.campaigns.close_and_open_daily_campaign")
def close_and_open_daily_campaign() -> dict:
    """Close yesterday's campaign and provision today's, per salon."""

    from apps.promotions.models import CampaignStatus, DailyCampaign
    from apps.promotions.services import (
        CampaignNotConfigured,
        close_campaign,
        provision_campaign,
        salon_today,
    )
    from apps.salons.models import Salon

    closed = 0
    opened = 0

    for salon in Salon.objects.filter(status=Salon.Status.ACTIVE):
        today = salon_today(salon)

        stale = DailyCampaign.objects.filter(
            salon=salon,
            status=CampaignStatus.ACTIVE,
            campaign_date__lt=today,
        )
        for campaign in stale:
            close_campaign(campaign)
            closed += 1

        try:
            provision_campaign(salon, today)
            opened += 1
        except CampaignNotConfigured:
            # An unconfigured salon is an owner problem, not a task failure --
            # log it and keep going so one salon cannot block the others.
            logger.error(
                "campaign_not_configured",
                extra={"salon_id": str(salon.pk), "campaign_date": today.isoformat()},
            )

    logger.info("daily_campaign_rollover", extra={"closed": closed, "opened": opened})
    return {"closed": closed, "opened": opened}


@shared_task(name="tasks.campaigns.expire_stale_reservations")
def expire_stale_reservations() -> int:
    """Release holds whose TTL has passed, freeing capacity."""
    from apps.promotions.services import expire_stale_reservations as expire

    freed = expire()
    if freed:
        logger.info("reservations_expired", extra={"count": freed})
    return freed
