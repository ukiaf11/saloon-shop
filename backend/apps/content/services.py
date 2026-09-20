"""Content write services.

Framework-independent (REQUIREMENTS.md 3.2): these take models and primitives,
never a DRF request, so the admin API, the seed command and a shell session all
go through the same path -- and therefore all invalidate the same cache keys.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.content.models import LegalPage, SiteContent
from common.cache import KEY_SALON, invalidate, legal_key


def invalidate_after_commit(*keys: str) -> None:
    """Drop public cache keys once the writing transaction commits.

    Deleting inline would open a window in which a concurrent reader misses the
    cache, rebuilds the payload from the *pre-commit* state and stores it --
    leaving stale content served until the TTL backstop expires. ``on_commit``
    runs immediately when there is no open transaction, so callers outside a
    transaction are unaffected.
    """
    transaction.on_commit(lambda: invalidate(*keys))


def publish_legal_page(
    salon,
    slug: str,
    title: str,
    body_markdown: str,
    actor=None,
) -> LegalPage:
    """Publish new copy for ``slug`` as the next version.

    Never edits an existing row: the version in force when an order was placed
    must remain readable (REQUIREMENTS.md 2.2).
    """
    with transaction.atomic():
        # Lock the existing versions so two concurrent publishes cannot read
        # the same max. The unique constraint on (salon, slug, version) is the
        # actual guarantee -- there is no row to lock for the very first
        # version, and per invariant 4 idempotency comes from the database,
        # not from an application-level check.
        existing = LegalPage.objects.select_for_update().filter(salon=salon, slug=slug)
        current_max = existing.aggregate(latest=Max("version"))["latest"]

        page = LegalPage.objects.create(
            salon=salon,
            slug=slug,
            title=title,
            body_markdown=body_markdown,
            version=(current_max or 0) + 1,
            published_at=timezone.now(),
            published_by=actor,
        )
        invalidate_after_commit(legal_key(slug))

    return page


def set_site_content(salon, key: str, value: Any, actor=None) -> SiteContent:
    """Create or update one content slot.

    Invalidates the salon payload rather than a content-specific key: site
    content is served inside ``GET /api/v1/salon`` (API_CONTRACT_PHASE2.md).
    """
    content, _ = SiteContent.objects.update_or_create(
        salon=salon,
        key=key,
        defaults={"value": value, "updated_by": actor},
    )
    invalidate_after_commit(KEY_SALON)
    return content
