from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import UUIDTimestampedModel


class PaymentProvider(models.TextChoices):
    # Phase 5 adds the gateway providers alongside this one.
    MANUAL_UPI = "MANUAL_UPI", "UPI QR (confirmed by the salon)"


class PaymentStatus(models.TextChoices):
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION", "Awaiting confirmation"
    CONFIRMED = "CONFIRMED", "Confirmed"
    REJECTED = "REJECTED", "Rejected"


#: Statuses in which a payment still stands for real money. A rejected claim
#: frees its UPI reference and its order for another attempt.
LIVE_PAYMENT_STATUSES = (PaymentStatus.AWAITING_CONFIRMATION, PaymentStatus.CONFIRMED)


class PaymentSettings(UUIDTimestampedModel):
    """How customers pay while no gateway is configured.

    The QR image is stored in the database rather than as a media file: the
    API runs on serverless functions with no persistent disk, it is one small
    image per salon, and keeping it beside the settings that govern it means
    there is no second system to lose it in.
    """

    salon = models.OneToOneField(
        "salons.Salon", on_delete=models.CASCADE, related_name="payment_settings"
    )
    qr_image = models.BinaryField(null=True, blank=True)
    qr_content_type = models.CharField(max_length=32, blank=True)
    qr_sha256 = models.CharField(max_length=64, blank=True)
    qr_width = models.PositiveIntegerField(null=True, blank=True)
    qr_height = models.PositiveIntegerField(null=True, blank=True)
    qr_updated_at = models.DateTimeField(null=True, blank=True)

    # Optional. With a UPI ID the checkout can also offer a "pay in your UPI
    # app" link with the exact amount filled in -- which matters on a phone,
    # where the customer cannot scan a QR shown on their own screen.
    upi_id = models.CharField(max_length=100, blank=True)
    payee_name = models.CharField(max_length=100, blank=True)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "payment_settings"

    def __str__(self) -> str:
        return f"payment settings for {self.salon_id}"

    @property
    def has_qr(self) -> bool:
        return bool(self.qr_sha256)


class Payment(UUIDTimestampedModel):
    """One attempt to pay for an order.

    For a UPI QR payment the customer pays in their own app, then gives us the
    transaction's 12-digit reference (UTR). Nothing is trusted until the owner
    finds that payment in their account and confirms it here -- only then does
    the order become PAID and enter the draw.
    """

    salon = models.ForeignKey("salons.Salon", on_delete=models.PROTECT, related_name="payments")
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=24, choices=PaymentProvider.choices)
    status = models.CharField(
        max_length=24,
        choices=PaymentStatus.choices,
        default=PaymentStatus.AWAITING_CONFIRMATION,
    )
    # The order total when the claim was made. The owner checks the money that
    # arrived against this figure.
    amount_paise = models.BigIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    reference = models.CharField(max_length=64)

    submitted_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_decided",
    )
    rejection_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "payment"
        ordering = ["-submitted_at"]
        indexes = [models.Index(fields=["status", "-submitted_at"])]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount_paise__gte=0), name="ck_payment_amount_non_negative"
            ),
            # One real payment backs one order. Without this, a single UPI
            # transfer could be claimed against two bookings.
            models.UniqueConstraint(
                fields=["provider", "reference"],
                condition=models.Q(status__in=LIVE_PAYMENT_STATUSES),
                name="uniq_payment_live_reference",
            ),
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(status__in=LIVE_PAYMENT_STATUSES),
                name="uniq_payment_one_live_per_order",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_provider_display()} {self.status} ({self.amount_paise} paise)"
