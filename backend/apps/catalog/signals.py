"""Cache invalidation for writes that do not go through apps.catalog.services.

The service layer already invalidates. These receivers are the safety net for
everything else -- a shell session, a data migration, a future admin view that
forgets -- because a stale ``/services`` payload means the site advertises a
price the order engine will not honour.
"""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.catalog.models import Service, ServiceCategory
from apps.catalog.services import invalidate_services_cache


@receiver(post_save, sender=Service)
@receiver(post_save, sender=ServiceCategory)
@receiver(post_delete, sender=Service)
@receiver(post_delete, sender=ServiceCategory)
def invalidate_on_catalog_write(sender, instance, **kwargs) -> None:
    invalidate_services_cache()
