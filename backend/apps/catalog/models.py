from __future__ import annotations

from django.conf import settings
from django.db import models

from common.exceptions import DomainError
from common.images import validate_image_file
from common.models import UUIDTimestampedModel

# Sentinel for "we never loaded the persisted price", which is not the same as
# "the persisted price is None".
_UNKNOWN = object()


class PriceChangeNotAudited(DomainError):
    """A price change reached Service.save() without an audit row.

    REQUIREMENTS.md 2.2 makes ServicePriceHistory mandatory, never optional.
    An unguarded ``service.price_paise = x; service.save()`` silently loses the
    old price, the actor and the reason -- and past orders keep their own
    snapshots, so nothing else in the schema can reconstruct what happened.
    """

    code = "price_change_not_audited"
    message = "Use apps.catalog.services.change_service_price() to change a price."


class ServiceCategory(UUIDTimestampedModel):
    """Grouping for the public service list. Optional: a service may be
    uncategorised (REQUIREMENTS.md 2.2)."""

    salon = models.ForeignKey(
        "salons.Salon", on_delete=models.CASCADE, related_name="service_categories"
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "service_category"
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "slug"], name="uniq_service_category_salon_slug"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Service(UUIDTimestampedModel):
    """A sellable service.

    ``price_paise`` is an integer number of paise and is only ever changed
    through ``apps.catalog.services.change_service_price`` -- see ``save``.
    """

    salon = models.ForeignKey("salons.Salon", on_delete=models.CASCADE, related_name="services")
    # SET_NULL: retiring a category must not delete the services priced under
    # it; they fall back to uncategorised.
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    price_paise = models.BigIntegerField()
    duration_minutes = models.IntegerField(default=30)
    image = models.ImageField(
        upload_to="catalog/services/",
        blank=True,
        validators=[validate_image_file],
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "service"
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["salon", "slug"], name="uniq_service_salon_slug"),
            models.CheckConstraint(
                check=models.Q(price_paise__gte=0), name="ck_service_price_paise_non_negative"
            ),
            models.CheckConstraint(
                check=models.Q(duration_minutes__gte=0),
                name="ck_service_duration_minutes_non_negative",
            ),
        ]
        indexes = [
            # The public catalogue query: active services for a salon in display
            # order. Every page load runs it on a cache miss.
            models.Index(
                fields=["salon", "is_active", "display_order"], name="ix_service_salon_active_order"
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Refuse a price change that has not been through the service layer.

        The guard is deliberately in ``save`` rather than in a reviewer's
        memory: the price history is a compliance record, and the cheapest way
        to lose it is an ad-hoc ``.save()`` in a shell or a future admin view.

        It catches the realistic mistake -- load, assign, save. It cannot catch
        ``QuerySet.update()``, which bypasses ``save`` entirely, nor a write
        from an instance that never loaded the old price, because in both cases
        there is no old price to record. REQUIREMENTS.md 2.2 allows a database
        trigger instead if those paths ever become a real risk.
        """
        authorised = self._price_change_authorised
        self._price_change_authorised = False

        persisted = getattr(self, "_persisted_price_paise", _UNKNOWN)
        if (
            not authorised
            and not self._state.adding
            and persisted is not _UNKNOWN
            and persisted != self.price_paise
        ):
            raise PriceChangeNotAudited(service_id=str(self.pk))

        super().save(*args, **kwargs)
        self._persisted_price_paise = self.price_paise

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._price_change_authorised = False

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._persisted_price_paise = (
            instance.price_paise if "price_paise" in field_names else _UNKNOWN
        )
        return instance

    def refresh_from_db(self, using=None, fields=None, **kwargs):
        # Django rebuilds a *separate* instance to refresh from, so without this
        # the tracked price would stay at the pre-refresh value and a legitimate
        # later save would be rejected.
        super().refresh_from_db(using=using, fields=fields, **kwargs)
        if fields is None or "price_paise" in fields:
            self._persisted_price_paise = self.price_paise

    def mark_price_change_authorised(self) -> None:
        """Allow exactly one ``save()`` to carry a new price.

        Only ``apps.catalog.services.change_service_price`` may call this, and
        only after it has written the ``ServicePriceHistory`` row. The flag is
        cleared by ``save``, so it cannot leak into a later write.
        """
        self._price_change_authorised = True


class ServicePriceHistory(UUIDTimestampedModel):
    """Append-only audit trail of every price change.

    Past orders keep their own price snapshots (invariant 8), so this table is
    the only place the *sequence* of prices survives -- it answers "what was
    this service priced at on the 3rd, and who changed it".
    """

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="price_history")
    old_price_paise = models.BigIntegerField()
    new_price_paise = models.BigIntegerField()
    # SET_NULL: the audit row outlives the staff account that caused it.
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_price_changes",
    )
    # auto_now_add, not a caller-supplied value: an audit timestamp nobody can
    # backdate. created_at exists on the base class but is generic bookkeeping;
    # reports and the admin trail read changed_at.
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reason = models.TextField(blank=True)

    class Meta:
        db_table = "service_price_history"
        ordering = ["-changed_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(old_price_paise__gte=0) & models.Q(new_price_paise__gte=0),
                name="ck_service_price_history_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["service", "-changed_at"], name="ix_price_history_service_time"),
        ]

    def __str__(self) -> str:
        return f"{self.service_id}: {self.old_price_paise} -> {self.new_price_paise}"
