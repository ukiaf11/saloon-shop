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

from rest_framework.throttling import ScopedRateThrottle

logger = logging.getLogger(__name__)


class ResilientScopedRateThrottle(ScopedRateThrottle):
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
