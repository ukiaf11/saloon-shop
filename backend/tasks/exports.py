"""Async report export generation. Implemented in Phase 8."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.exports.generate_export")
def generate_export(export_job_id: str) -> None:
    logger.info("export_task_stub", extra={"export_job_id": export_job_id})
