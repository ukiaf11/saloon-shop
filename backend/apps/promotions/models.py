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
