"""Coupon lifecycle tasks. Implemented in Phase 6."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.coupons.expire_coupons")
def expire_coupons() -> None:
    """Move coupons past valid_until to EXPIRED."""
    logger.info("coupon_task_stub", extra={"task": "expire_coupons"})
