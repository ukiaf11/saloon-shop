"""Rate limiting that survives a cache outage.

DRF's throttles read and write the cache on every request, and Django's Redis
backend raises when Redis is unreachable. Left alone, a Redis restart -- routine
on a managed platform -- turns every API call into a 500, including the public
pages. That defeats the rest of the system's care to make Redis a performance
dependency rather than an availability one (see common/cache.py).

So throttling fails OPEN: if the counter cannot be read, the request is allowed
and the failure is logged at ERROR for alerting. That trades a brief window with
no rate limit for keeping the site up, which is the right trade for a salon's
booking page. It is the wrong trade for anything where an unthrottled burst is
itself the damage -- revisit this before rate-limiting OTP sends or admin login
purely on this class.
"""

from __future__ import annotations

import logging
import re

from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import ScopedRateThrottle

logger = logging.getLogger(__name__)

_PERIOD = re.compile(r"^(\d*)\s*([smhd])", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class ResilientScopedRateThrottle(ScopedRateThrottle):
    def parse_rate(self, rate):
        """Accept a multiplied period such as "5/15min" as well as "10/min".

        DRF reads only the first character of the period, so "15min" became a
        KeyError on "1" -- which allow_request below then swallowed, leaving
        that scope silently unthrottled and logging a misleading cache error.
        """
        if rate is None:
            return (None, None)
        num, period = rate.split("/")
        match = _PERIOD.match(period.strip())
        if match is None:
            raise ImproperlyConfigured(f"Unparseable throttle rate {rate!r}.")
        multiplier = int(match.group(1) or 1)
        return int(num), multiplier * _UNIT_SECONDS[match.group(2).lower()]

    def allow_request(self, request, view) -> bool:
        try:
            return super().allow_request(request, view)
        except Exception:
            logger.error(
                "throttle_cache_unavailable",
                extra={"scope": getattr(view, "throttle_scope", None)},
                exc_info=True,
            )
            return True
