"""Cache invalidation for owner edits.

Attached to the models rather than to the admin views so that a fix applied
from a shell or a data migration cannot leave the public site serving stale
content. Deletes are covered too: an unpublished testimonial that keeps
appearing is the same bug as a missing one.
"""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.content.models import FaqItem, GalleryImage, SiteContent, Testimonial
from apps.content.services import invalidate_after_commit
from common.cache import KEY_FAQS, KEY_GALLERY, KEY_SALON, KEY_TESTIMONIALS


@receiver(post_save, sender=GalleryImage)
@receiver(post_delete, sender=GalleryImage)
def invalidate_gallery(**_kwargs) -> None:
    invalidate_after_commit(KEY_GALLERY)


@receiver(post_save, sender=Testimonial)
@receiver(post_delete, sender=Testimonial)
def invalidate_testimonials(**_kwargs) -> None:
    invalidate_after_commit(KEY_TESTIMONIALS)


@receiver(post_save, sender=FaqItem)
@receiver(post_delete, sender=FaqItem)
def invalidate_faqs(**_kwargs) -> None:
    invalidate_after_commit(KEY_FAQS)


@receiver(post_save, sender=SiteContent)
@receiver(post_delete, sender=SiteContent)
def invalidate_site_content(**_kwargs) -> None:
    # Site content is served inside GET /api/v1/salon, not under a key of its
    # own (API_CONTRACT_PHASE2.md).
    invalidate_after_commit(KEY_SALON)
