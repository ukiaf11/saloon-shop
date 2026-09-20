"""Public cache invalidation for salon profile changes.

The /salon payload is assembled from Salon, BusinessHour and content.SiteContent.
The content app invalidates KEY_SALON for its own writes; these receivers cover
the other two, so an owner's address or opening-hour edit is visible on the next
request rather than after the TTL backstop.
"""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.salons.models import BusinessHour, Salon
from common.cache import KEY_SALON, invalidate


@receiver(post_save, sender=Salon)
@receiver(post_delete, sender=Salon)
@receiver(post_save, sender=BusinessHour)
@receiver(post_delete, sender=BusinessHour)
def invalidate_salon_cache(**_kwargs) -> None:
    invalidate(KEY_SALON)
