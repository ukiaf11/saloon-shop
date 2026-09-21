from __future__ import annotations

import secrets

from django.db import models

from apps.orders.state import OrderStatus, check_transition
from common.models import UUIDTimestampedModel

# No I/O/0/1: an order number gets read aloud over a phone and copied off a
# screen, so the ambiguous glyphs are worth losing.
_SUFFIX_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_public_order_number(today) -> str:
    """SL-YYMMDD-XXXX.

    The suffix is random rather than sequential on purpose: a sequential order
    number tells every customer how many orders the salon has taken, which is
    business information they should not get from a receipt.
    """
    suffix = "".join(secrets.choice(_SUFFIX_ALPHABET) for _ in range(4))
    return f"SL-{today:%y%m%d}-{suffix}"


class Order(UUIDTimestampedModel):
    salon = models.ForeignKey("salons.Salon", on_delete=models.PROTECT, related_name="orders")
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    # The day this order belongs to. Nullable because an order is created
    # before capacity is reserved, and because a purchase that does not enter
    # the campaign legitimately has none.
    daily_campaign = models.ForeignKey(
        "promotions.DailyCampaign",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )
    # The configuration that priced this order. Kept so the discount can be
    # justified months later without guessing which settings were in force.
    campaign_config = models.ForeignKey(
        "promotions.CampaignConfig",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )

    public_order_number = models.CharField(max_length=20, unique=True)

    subtotal_paise = models.BigIntegerField()
    discount_paise = models.BigIntegerField(default=0)
    total_paise = models.BigIntegerField()
    discount_percent_applied = models.PositiveSmallIntegerField(default=0)

    status = models.CharField(max_length=24, choices=OrderStatus.choices, default=OrderStatus.DRAFT)

    # Distinguishes a normal purchase from a campaign entry. Doc 2 section 28
    # requires the two to stay separable: a customer may buy repeatedly while
    # only the first order of the day enters the draw.
    enters_lucky_campaign = models.BooleanField(default=True)

    # Replaying a create request with the same key returns the original order
    # rather than making a second one.
    idempotency_key = models.CharField(max_length=128, null=True, blank=True, unique=True)

    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "order"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["salon", "-created_at"]),
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(subtotal_paise__gte=0),
                name="ck_order_subtotal_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(discount_paise__gte=0),
                name="ck_order_discount_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(total_paise__gte=0),
                name="ck_order_total_non_negative",
            ),
            # The arithmetic is enforced by the database, not just by the code
            # that writes it. Any future path that computes a total wrongly
            # fails loudly here instead of charging the wrong amount.
            models.CheckConstraint(
                check=models.Q(total_paise=models.F("subtotal_paise") - models.F("discount_paise")),
                name="ck_order_total_equals_subtotal_minus_discount",
            ),
        ]

    def __str__(self) -> str:
        return self.public_order_number

    def transition_to(self, target: str, *, save: bool = True) -> None:
        """Move to `target`, refusing any edge not in the state table."""
        check_transition(self.status, target)
        self.status = target
        if save:
            self.save(update_fields=["status", "updated_at"])


class OrderItem(UUIDTimestampedModel):
    """A priced line, snapshotted.

    `service` is kept for reporting, but every value shown to a customer or used
    in a refund comes from the snapshot columns. If the owner renames Haircut or
    raises it from 300 to 350 tomorrow, this row must still say what was sold
    and what was charged (Doc 2 section 4).
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    service = models.ForeignKey(
        "catalog.Service", on_delete=models.PROTECT, related_name="order_items"
    )

    service_name_snapshot = models.CharField(max_length=200)
    service_slug_snapshot = models.SlugField(max_length=200)
    unit_price_paise = models.BigIntegerField()
    quantity = models.PositiveSmallIntegerField(default=1)
    line_total_paise = models.BigIntegerField()

    # The order-level discount's share of this line, by largest remainder
    # (REQUIREMENTS.md 8.3). net_paid is what a winner refund is measured
    # against (8.1), so it is stored rather than recomputed on read.
    discount_alloc_paise = models.BigIntegerField(default=0)
    net_paid_paise = models.BigIntegerField()

    class Meta:
        db_table = "order_item"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=1), name="ck_order_item_quantity_min"
            ),
            models.CheckConstraint(
                check=models.Q(unit_price_paise__gte=0),
                name="ck_order_item_unit_price_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(
                    line_total_paise=models.F("unit_price_paise") * models.F("quantity")
                ),
                name="ck_order_item_line_total_matches",
            ),
            models.CheckConstraint(
                check=models.Q(
                    net_paid_paise=models.F("line_total_paise") - models.F("discount_alloc_paise")
                ),
                name="ck_order_item_net_paid_matches",
            ),
            models.CheckConstraint(
                check=models.Q(discount_alloc_paise__gte=0),
                name="ck_order_item_discount_alloc_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service_name_snapshot} x{self.quantity}"
