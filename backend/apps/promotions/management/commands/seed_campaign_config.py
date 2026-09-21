"""Create the initial campaign configuration.

Idempotent: re-running does not stack duplicate rows for the same date.
"""

from __future__ import annotations

import datetime as dt

from django.core.management.base import BaseCommand, CommandError

from apps.promotions.models import CampaignConfig, RewardType
from apps.salons.models import Salon


class Command(BaseCommand):
    help = "Seed the initial CampaignConfig for the salon."

    def add_arguments(self, parser):
        parser.add_argument("--capacity", type=int, default=40)
        parser.add_argument("--lucky", type=int, default=5)
        parser.add_argument("--discount", type=int, default=10)
        parser.add_argument("--min-services", type=int, default=2)

    def handle(self, *args, **options):
        salon = Salon.objects.first()
        if salon is None:
            raise CommandError("No salon found. Run seed_salon first.")

        if options["lucky"] > options["capacity"]:
            raise CommandError("lucky_count cannot exceed daily_capacity.")

        effective_from = dt.date(2000, 1, 1)  # covers every past and present date
        existing = CampaignConfig.objects.filter(salon=salon, effective_from=effective_from).first()
        if existing:
            self.stdout.write(f"exists: campaign config from {effective_from}")
            return

        config = CampaignConfig.objects.create(
            salon=salon,
            daily_capacity=options["capacity"],
            lucky_count=options["lucky"],
            discount_percent=options["discount"],
            min_distinct_services=options["min_services"],
            reward_type=RewardType.SERVICE_PACKAGE,
            reward_definition={"service_slugs": ["hair-cutting", "shaving", "face-massage"]},
            effective_from=effective_from,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"created: capacity {config.daily_capacity}, "
                f"{config.lucky_count} lucky slots, "
                f"{config.discount_percent}% off {config.min_distinct_services}+ services"
            )
        )
