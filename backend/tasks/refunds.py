"""Refund retry ladder. Implemented in Phase 7.

Schedule: immediate -> 1m -> 5m -> 30m -> 2h -> MANUAL_REVIEW_REQUIRED.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

RETRY_BACKOFF_SECONDS = (0, 60, 300, 1800, 7200)


@shared_task(name="tasks.refunds.retry_pending_refunds")
def retry_pending_refunds() -> None:
    logger.info("refund_task_stub", extra={"task": "retry_pending_refunds"})
