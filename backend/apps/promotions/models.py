from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import UUIDTimestampedModel


class RewardType(models.TextChoices):
    # Only SERVICE_PACKAGE is active in V1 (Doc 2 section 20). The others are
    # named now so the stored value never has to be migrated later.
    SERVICE_PACKAGE = "SERVICE_PACKAGE", "Service package"
    FIXED_DISCOUNT = "FIXED_DISCOUNT", "Fixed discount"
    PERCENT_DISCOUNT = "PERCENT_DISCOUNT", "Percent discount"
    FIXED_CREDIT = "FIXED_CREDIT", "Fixed credit"


class CampaignConfig(UUIDTimestampedModel):
    """Versioned, append-only campaign settings.

    Never edited in place. Changing a setting writes a new row with a later
    `effective_from`, so the configuration that governed any past order stays
    recoverable -- which is what makes a winner decision auditable after the
    fact (Doc 2 section 18).

    Reading "the config for date D" means: the latest row with
    `effective_from <= D`. See promotions.services.config_for.
    """

    salon = models.ForeignKey(
        "salons.Salon", on_delete=models.CASCADE, related_name="campaign_configs"
    )

    daily_capacity = models.PositiveIntegerField()
    lucky_count = models.PositiveIntegerField()
    discount_percent = models.PositiveSmallIntegerField(default=10)
    min_distinct_services = models.PositiveSmallIntegerField(default=2)
    max_entries_per_phone_per_day = models.PositiveSmallIntegerField(default=1)

    reward_type = models.CharField(
        max_length=32, choices=RewardType.choices, default=RewardType.SERVICE_PACKAGE
    )
    # {"service_slugs": ["hair-cutting", "shaving", "face-massage"]}
    reward_definition = models.JSONField(default=dict)

    coupon_validity_days = models.PositiveSmallIntegerField(default=30)

    effective_from = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_configs_created",
    )

    class Meta:
        db_table = "campaign_config"
        ordering = ["-effective_from", "-created_at"]
        indexes = [models.Index(fields=["salon", "-effective_from"])]
        constraints = [
            models.CheckConstraint(
                check=models.Q(daily_capacity__gt=0),
                name="ck_campaign_config_capacity_positive",
            ),
            # The spec's headline rule: you cannot promise more winners than
            # there are slots to win them in.
            models.CheckConstraint(
                check=models.Q(lucky_count__lte=models.F("daily_capacity")),
                name="ck_campaign_config_lucky_within_capacity",
            ),
            models.CheckConstraint(
                check=models.Q(discount_percent__gte=0, discount_percent__lte=100),
                name="ck_campaign_config_discount_percent_range",
            ),
            models.CheckConstraint(
                check=models.Q(min_distinct_services__gte=1),
                name="ck_campaign_config_min_distinct_at_least_one",
            ),
        ]

    def __str__(self) -> str:
        return f"config from {self.effective_from} ({self.discount_percent}% off)"

    @property
    def reward_service_slugs(self) -> list[str]:
        return list(self.reward_definition.get("service_slugs", []))


class CampaignStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    ACTIVE = "ACTIVE", "Active"
    CLOSED = "CLOSED", "Closed"


class DailyCampaign(UUIDTimestampedModel):
    """One immutable day of the promotion.

    Created once per salon per date and never reset -- yesterday's record is
    history, not scratch space (Doc 1 section 3.3). The row is also the
    concurrency anchor: capacity admission locks it with SELECT ... FOR UPDATE,
    so the last slot cannot be sold twice.

    The seed and the winning positions are encrypted at rest and must never
    appear in an API response, a serializer, a log line or an admin screen.
    `seed_commitment` is the one public artefact: it proves after the fact that
    the positions were fixed before anyone played.
    """

    salon = models.ForeignKey(
        "salons.Salon", on_delete=models.PROTECT, related_name="daily_campaigns"
    )
    config = models.ForeignKey(
        CampaignConfig, on_delete=models.PROTECT, related_name="daily_campaigns"
    )
    campaign_date = models.DateField()

    # Snapshotted from the config at creation. Reading them off the live config
    # later would let a settings change rewrite a day that has already run.
    capacity = models.PositiveIntegerField()
    lucky_count = models.PositiveIntegerField()
    discount_percent = models.PositiveSmallIntegerField()
    min_distinct_services = models.PositiveSmallIntegerField()
    reward_snapshot = models.JSONField(default=dict)

    status = models.CharField(
        max_length=16, choices=CampaignStatus.choices, default=CampaignStatus.ACTIVE
    )

    seed_commitment = models.CharField(max_length=64)
    #: Fernet tokens. NEVER serialized. See common.crypto.
    encrypted_seed = models.TextField()
    encrypted_winning_positions = models.TextField()

    paid_count = models.PositiveIntegerField(default=0)
    winner_count = models.PositiveIntegerField(default=0)

    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "daily_campaign"
        ordering = ["-campaign_date"]
        constraints = [
            # The single most important constraint in the app: it is what makes
            # both the scheduled task and the lazy fallback safe to race.
            models.UniqueConstraint(
                fields=["salon", "campaign_date"], name="uniq_daily_campaign_salon_date"
            ),
            models.CheckConstraint(
                check=models.Q(capacity__gt=0), name="ck_daily_campaign_capacity_positive"
            ),
            models.CheckConstraint(
                check=models.Q(lucky_count__lte=models.F("capacity")),
                name="ck_daily_campaign_lucky_within_capacity",
            ),
            models.CheckConstraint(
                check=models.Q(paid_count__lte=models.F("capacity")),
                name="ck_daily_campaign_paid_within_capacity",
            ),
            models.CheckConstraint(
                check=models.Q(winner_count__lte=models.F("lucky_count")),
                name="ck_daily_campaign_winners_within_lucky_count",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.salon_id} {self.campaign_date} ({self.paid_count}/{self.capacity})"

    @property
    def is_locked(self) -> bool:
        """True once someone has paid: today's settings become immutable.

        Changing capacity or winner count mid-day would make the draw
        challengeable, so edits after this point apply from the next date
        (Doc 2 section 18).
        """
        return self.paid_count > 0

    @property
    def slots_remaining(self) -> int:
        return max(self.capacity - self.paid_count, 0)

    @property
    def winners_remaining(self) -> int:
        return max(self.lucky_count - self.winner_count, 0)


class ReservationStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    CONSUMED = "CONSUMED", "Consumed"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"


class SlotReservation(UUIDTimestampedModel):
    """A temporary hold on one of the day's slots.

    Without it, five people reaching checkout when one slot remains would all
    see it available and all pay (Doc 2 section 6). A reservation is taken under
    the campaign row lock, expires if payment does not follow, and is consumed
    when it does.
    """

    daily_campaign = models.ForeignKey(
        DailyCampaign, on_delete=models.CASCADE, related_name="reservations"
    )
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="slot_reservation",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="slot_reservations",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=16, choices=ReservationStatus.choices, default=ReservationStatus.ACTIVE
    )
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "slot_reservation"
        indexes = [
            # The hot path: counting live holds for a campaign. Partial, because
            # consumed and expired rows accumulate forever and are never counted.
            models.Index(
                fields=["daily_campaign"],
                condition=models.Q(status="ACTIVE"),
                name="ix_slot_reservation_active",
            ),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.status} until {self.expires_at:%H:%M}"

    @property
    def is_live(self) -> bool:
        from django.utils import timezone

        return self.status == ReservationStatus.ACTIVE and self.expires_at > timezone.now()


class LuckyDecision(UUIDTimestampedModel):
    """The outcome of one verified payment's entry into its day's draw.

    Written once, inside the same transaction that bumps the campaign's
    paid_count, and never updated (Doc 2 section 16). participant_number is the
    order's position in that day's paid sequence; it wins when it is one of
    the positions drawn -- and committed to -- before the day began.
    """

    daily_campaign = models.ForeignKey(
        DailyCampaign, on_delete=models.PROTECT, related_name="decisions"
    )
    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="lucky_decision"
    )
    participant_number = models.PositiveIntegerField()
    is_winner = models.BooleanField()
    # A winner's refund under the reward-attributable rule (REQUIREMENTS.md
    # 8.1): what they paid, after discount, for purchased services that are in
    # the reward package. Zero for a non-winner.
    reward_refund_paise = models.BigIntegerField(default=0)
    # Package services the winner did not buy, which they get free. Names are
    # snapshotted so a later rename cannot change what was promised.
    free_services = models.JSONField(default=list, blank=True)
    decided_at = models.DateTimeField()

    class Meta:
        db_table = "lucky_decision"
        ordering = ["daily_campaign", "participant_number"]
        constraints = [
            # Two orders can never share a draw number on the same day.
            models.UniqueConstraint(
                fields=["daily_campaign", "participant_number"],
                name="uniq_lucky_decision_participant",
            ),
            models.CheckConstraint(
                check=models.Q(participant_number__gte=1),
                name="ck_lucky_decision_participant_positive",
            ),
            models.CheckConstraint(
                check=models.Q(reward_refund_paise__gte=0),
                name="ck_lucky_decision_refund_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(is_winner=True) | models.Q(reward_refund_paise=0),
                name="ck_lucky_decision_refund_only_for_winners",
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.participant_number} {'won' if self.is_winner else 'no win'}"
