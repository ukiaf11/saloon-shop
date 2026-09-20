"""Daily campaign lifecycle tasks. Implemented in Phase 4."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.campaigns.close_and_open_daily_campaign")
def close_and_open_daily_campaign() -> None:
    """Close yesterday's campaign and provision today's (00:00 Asia/Kolkata).

    Idempotent against UNIQUE (salon_id, campaign_date); the lazy provisioning
    path in apps.promotions may have already created today's row.
    """
    logger.info("campaign_task_stub", extra={"task": "close_and_open_daily_campaign"})


@shared_task(name="tasks.campaigns.expire_stale_reservations")
def expire_stale_reservations() -> None:
    """Flip ACTIVE reservations past their TTL to EXPIRED, freeing capacity."""
    logger.info("campaign_task_stub", extra={"task": "expire_stale_reservations"})
