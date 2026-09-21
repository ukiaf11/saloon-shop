"""Scheduled jobs, triggered over HTTP by Vercel Cron.

Replaces Celery Beat on Vercel, which cannot run a long-lived scheduler. The
schedule lives in backend/vercel.json: "0 19 * * *" UTC. On the Hobby plan a
daily job fires somewhere in that hour, i.e. 00:30-01:29 IST -- always after
midnight in India, which is what matters. An earlier slot could fire at 23:30
IST and close the wrong day.

Missing a run is safe: today's campaign is also created on the first request
of the day, and reserve_slot() already ignores expired holds. This job tidies
up; it is not the only guarantee.
"""

from __future__ import annotations

import logging
import os

from django.http import JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

#: A shorter secret is treated as a misconfiguration, not as a password.
MIN_SECRET_LENGTH = 16


def _authorised(request) -> bool:
    """Vercel sends `Authorization: Bearer <CRON_SECRET>`. Fails closed: with no
    secret configured, nobody can trigger the job -- not even with an empty
    header matching an empty secret."""
    secret = os.environ.get("CRON_SECRET", "")
    if len(secret) < MIN_SECRET_LENGTH:
        return False
    return constant_time_compare(request.headers.get("Authorization", ""), f"Bearer {secret}")


@require_GET
def daily_rollover(request):
    # A plain Django view, not DRF: no session auth, no throttling, no CSRF
    # machinery in the way of a machine caller.
    if not _authorised(request):
        return JsonResponse(
            {"error": {"code": "unauthorized", "message": "Unauthorized."}}, status=401
        )

    from tasks.campaigns import close_and_open_daily_campaign, expire_stale_reservations

    # Called directly, in process: there is no broker or worker on Vercel.
    result = dict(close_and_open_daily_campaign())
    result["reservations_expired"] = expire_stale_reservations()
    logger.info("cron_daily_rollover", extra=result)
    return JsonResponse(result)
