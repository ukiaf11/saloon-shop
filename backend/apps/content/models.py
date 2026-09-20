"""Owner-editable website content.

Everything the public page renders outside the service catalog lives here, so
the owner can change copy, photos, testimonials and FAQs without a deploy.

``LegalPage`` is the exception to "just content": it is versioned and treated as
append-only, because the promotion rules in force at the time of a given order
have to stay recoverable long after the owner has rewritten them
(REQUIREMENTS.md 2.2).
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.images import validate_image_file
from common.models import UUIDTimestampedModel


class SiteContent(UUIDTimestampedModel):
    """A single editable content slot, keyed by name.

    Key/value rather than a wide table: the hero copy, the "why choose us"
    cards and the social links all change shape independently, and a new slot
    must not require a migration. The keys the public payload expects are
    documented in API_CONTRACT_PHASE2.md (``GET /api/v1/salon``).
    """

    salon = models.ForeignKey("salons.Salon", on_delete=models.CASCADE, related_name="site_content")
    key = models.SlugField(max_length=64)
    value = models.JSONField()
    updated_by = models.ForeignKey(
        "accounts.AdminUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "site_content"
        ordering = ["key"]
        constraints = [
            models.UniqueConstraint(fields=["salon", "key"], name="uniq_site_content_salon_key"),
        ]

    def __str__(self) -> str:
        return self.key


class GalleryImage(UUIDTimestampedModel):
    salon = models.ForeignKey(
        "salons.Salon", on_delete=models.CASCADE, related_name="gallery_images"
    )
    image = models.ImageField(upload_to="gallery/", validators=[validate_image_file])
    # Not optional: a gallery of undescribed photos is unusable with a screen
    # reader, and there is no sensible fallback the frontend could invent.
    alt_text = models.CharField(max_length=255)
    caption = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "gallery_image"
        ordering = ["display_order", "created_at"]
        indexes = [models.Index(fields=["salon", "is_active", "display_order"])]

    def __str__(self) -> str:
        return self.alt_text

    def save(self, *args, **kwargs):
        # The frontend reserves layout space from these to avoid CLS
        # (API_CONTRACT_PHASE2.md), so record them once at write time.
        # Django's width_field/height_field hook would re-read the file on
        # every post_init instead, which raises for any row whose file has
        # since gone missing from storage -- dimensions are a nice-to-have and
        # must never be able to break loading or saving the row.
        if self.image and (self.width is None or self.height is None):
            try:
                self.width, self.height = self.image.width, self.image.height
            except Exception:
                self.width = self.height = None
        super().save(*args, **kwargs)


class Testimonial(UUIDTimestampedModel):
    salon = models.ForeignKey("salons.Salon", on_delete=models.CASCADE, related_name="testimonials")
    author_name = models.CharField(max_length=120)
    # Validators as well as the CHECK constraint: the constraint is the
    # guarantee, the validators turn a bad admin payload into a 400 instead of
    # an IntegrityError surfacing as a 409.
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    body = models.TextField()
    is_published = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "testimonial"
        ordering = ["display_order", "created_at"]
        indexes = [models.Index(fields=["salon", "is_published", "display_order"])]
        constraints = [
            models.CheckConstraint(
                check=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name="ck_testimonial_rating_1_5",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.author_name} ({self.rating}/5)"


class FaqItem(UUIDTimestampedModel):
    salon = models.ForeignKey("salons.Salon", on_delete=models.CASCADE, related_name="faq_items")
    question = models.CharField(max_length=300)
    answer = models.TextField()
    is_published = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "faq_item"
        ordering = ["display_order", "created_at"]
        indexes = [models.Index(fields=["salon", "is_published", "display_order"])]

    def __str__(self) -> str:
        return self.question


class LegalPage(UUIDTimestampedModel):
    """One version of one legal document.

    Rows are never edited in place: publishing new copy writes a new version
    (see ``services.publish_legal_page``). A dispute about an order from three
    months ago has to be answerable with the promotion rules that were actually
    in force then, and that is only possible if the old row still exists.

    ``published_at is None`` means draft -- the public endpoint ignores it.
    """

    class Slug(models.TextChoices):
        TERMS = "terms", "Terms of Service"
        PRIVACY = "privacy", "Privacy Policy"
        REFUNDS = "refunds", "Refund Policy"
        PROMOTION_RULES = "promotion-rules", "Promotion Rules"

    salon = models.ForeignKey("salons.Salon", on_delete=models.CASCADE, related_name="legal_pages")
    slug = models.CharField(max_length=32, choices=Slug.choices)
    title = models.CharField(max_length=200)
    body_markdown = models.TextField()
    version = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "accounts.AdminUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "legal_page"
        ordering = ["slug", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "slug", "version"], name="uniq_legal_page_salon_slug_version"
            ),
        ]
        indexes = [models.Index(fields=["salon", "slug", "-version"])]

    def __str__(self) -> str:
        return f"{self.slug} v{self.version}"
