"""Outbound SMS/WhatsApp dispatch. Implemented in Phase 6."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.notifications.send_notification")
def send_notification(notification_id: str) -> None:
    logger.info("notification_task_stub", extra={"notification_id": notification_id})
