"""Bootstrap a development salon and an owner account.

Deliberately refuses to run with a weak or defaulted password so a seeded
owner can never become a production foothold.
"""

from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.accounts.models import AdminUser, Role
from apps.salons.models import BusinessHour, Salon


class Command(BaseCommand):
    help = "Create the initial salon and owner account."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="Upendra Salon")
        parser.add_argument("--owner-email", default="owner@example.com")
        parser.add_argument("--owner-name", default="Salon Owner")

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("SEED_OWNER_PASSWORD")
        if not password or len(password) < 12:
            raise CommandError("Set SEED_OWNER_PASSWORD to a value of at least 12 characters.")

        name = options["name"]
        salon, created = Salon.objects.get_or_create(slug=slugify(name), defaults={"name": name})
        self.stdout.write(f"{'created' if created else 'exists'}: salon {salon.name}")

        for day in range(7):
            BusinessHour.objects.get_or_create(
                salon=salon,
                day_of_week=day,
                defaults={"open_time": "10:00", "close_time": "21:00"},
            )

        email = options["owner_email"].lower()
        if AdminUser.objects.filter(email=email).exists():
            self.stdout.write(f"exists: owner {email}")
            return

        AdminUser.objects.create_user(
            email=email,
            password=password,
            full_name=options["owner_name"],
            role=Role.OWNER,
            is_staff=True,
        )
        self.stdout.write(self.style.SUCCESS(f"created: owner {email}"))
        self.stdout.write(self.style.WARNING("Enable MFA for this account before production use."))
