"""Campaign configuration reads.

`config_for` is the single way to answer "what settings governed date D". Any
code that reaches for the newest CampaignConfig row directly will silently use
tomorrow's settings on today's order.
"""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from apps.promotions.models import CampaignConfig
from apps.salons.models import Salon
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
