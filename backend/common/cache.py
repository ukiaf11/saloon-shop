"""Public read-cache helpers.

The public site is read-heavy and its data changes rarely, so the catalog and
content endpoints are cached in Redis. Invalidation is *explicit*: a price
change must be visible on the next request, not after a TTL lapses
(API_CONTRACT_PHASE2.md). The TTL here is only a backstop against a missed
invalidation, never the primary mechanism.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Bump when a cached payload's shape changes, so a deploy cannot serve a stale
# structure to a newer frontend.
CACHE_VERSION = "v1"

DEFAULT_TTL_SECONDS = 15 * 60

# Every public cache key, so invalidation cannot silently miss one.
KEY_SALON = f"public:salon:{CACHE_VERSION}"
KEY_SERVICES = f"public:services:{CACHE_VERSION}"
KEY_GALLERY = f"public:gallery:{CACHE_VERSION}"
KEY_TESTIMONIALS = f"public:testimonials:{CACHE_VERSION}"
KEY_FAQS = f"public:faqs:{CACHE_VERSION}"


def legal_key(slug: str) -> str:
    return f"public:legal:{CACHE_VERSION}:{slug}"


def cached(key: str, builder: Callable[[], Any], ttl: int = DEFAULT_TTL_SECONDS) -> Any:
    """Return the cached payload for ``key``, building and storing it on a miss.

    A Redis outage must not take the public site down, so a cache failure falls
    through to building the payload directly.
    """
    try:
        hit = cache.get(key)
        if hit is not None:
            return hit
    except Exception:
        # A Redis outage degrades performance, never availability.
        logger.warning("cache_read_failed", extra={"cache_key": key}, exc_info=True)
        return builder()

    payload = builder()
    try:
        cache.set(key, payload, ttl)
    except Exception:
        logger.warning("cache_write_failed", extra={"cache_key": key}, exc_info=True)
    return payload


def invalidate(*keys: str) -> None:
    """Drop cached payloads. Safe to call inside a transaction."""
    try:
        cache.delete_many(list(keys))
    except Exception:
        # A failed invalidation is more serious than a failed read: stale
        # prices could be served until the TTL backstop expires.
        logger.error("cache_invalidate_failed", extra={"cache_keys": list(keys)}, exc_info=True)
