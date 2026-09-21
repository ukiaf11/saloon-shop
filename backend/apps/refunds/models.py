from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import UUIDTimestampedModel


class RefundReason(models.TextChoices):
    LUCKY_REWARD = "LUCKY_REWARD", "Lucky slot reward"


class RefundMethod(models.TextChoices):
    UPI = "UPI", "UPI transfer"
    CASH = "CASH", "Cash at the salon"


class RefundStatus(models.TextChoices):
    PENDING = "PENDING", "To be sent"
    SENT = "SENT", "Sent"


class Refund(UUIDTimestampedModel):
    """Money owed back to a customer.

    For a UPI QR payment there is no gateway to call, so a refund is a task for
    the owner: send it from their UPI app (or in cash), then record it here.
    The amount is fixed when the refund is created and never recomputed.
    """

    salon = models.ForeignKey("salons.Salon", on_delete=models.PROTECT, related_name="refunds")
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="refunds")
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="refunds",
        null=True,
        blank=True,
    )
    reason = models.CharField(max_length=24, choices=RefundReason.choices)
    amount_paise = models.BigIntegerField()
    status = models.CharField(
        max_length=16, choices=RefundStatus.choices, default=RefundStatus.PENDING
    )

    method = models.CharField(max_length=8, choices=RefundMethod.choices, blank=True)
    # The UTR of the refund transfer, when sent by UPI.
    reference = models.CharField(max_length=64, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refunds_sent",
    )

    class Meta:
        db_table = "refund"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount_paise__gt=0), name="ck_refund_amount_positive"
            ),
            # A win is refunded once. A second row for the same order and
            # reason would be a double payout.
            models.UniqueConstraint(fields=["order", "reason"], name="uniq_refund_order_reason"),
        ]

    def __str__(self) -> str:
        return f"{self.get_reason_display()} {self.amount_paise} paise ({self.status})"
