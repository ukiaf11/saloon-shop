"""Seed the salon's service catalogue.

Idempotent: re-running adds anything missing and leaves existing rows alone.
In particular it never rewrites a price -- that would bypass
``change_service_price`` and silently lose a history row.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Service, ServiceCategory
from apps.catalog.services import invalidate_services_cache
from apps.salons.models import Salon

CATEGORIES = [
    ("Hair", "hair", 1),
    ("Grooming", "grooming", 2),
    ("Skin", "skin", 3),
]

# (name, slug, category slug, price in paise, minutes, featured, order, description)
SERVICES = [
    (
        "Hair Cutting",
        "hair-cutting",
        "hair",
        30000,
        30,
        True,
        1,
        "Precision cut and finish by a trained stylist, wash included.",
    ),
    (
        "Shaving",
        "shaving",
        "grooming",
        15000,
        20,
        False,
        2,
        "Classic hot-towel shave with a fresh blade every time.",
    ),
    (
        "Face Massage",
        "face-massage",
        "skin",
        40000,
        30,
        False,
        3,
        "Relaxing face and neck massage with a cleanser and cold compress.",
    ),
    (
        "Hair Spa",
        "hair-spa",
        "hair",
        80000,
        60,
        True,
        4,
        "Deep-conditioning spa treatment with a scalp massage and steam.",
    ),
    (
        "Beard Trim",
        "beard-trim",
        "grooming",
        12000,
        20,
        False,
        5,
        "Shape-up and line-up, finished with beard oil.",
    ),
    (
        "Head Massage",
        "head-massage",
        "hair",
        35000,
        30,
        False,
        6,
        "Champi-style oil massage for the scalp, neck and shoulders.",
    ),
    (
        "Hair Colour",
        "hair-colour",
        "hair",
        120000,
        90,
        False,
        7,
        "Global colour or grey coverage using ammonia-free professional colour.",
    ),
    (
        "Facial",
        "facial",
        "skin",
        90000,
        60,
        True,
        8,
        "Cleanup, exfoliation, massage and pack matched to your skin type.",
    ),
]


class Command(BaseCommand):
    help = "Create the salon's service categories and services."

    @transaction.atomic
    def handle(self, *args, **options):
        salon = Salon.objects.order_by("created_at").first()
        if salon is None:
            raise CommandError("No salon exists. Run `manage.py seed_salon` first.")

        categories = {}
        for name, slug, order in CATEGORIES:
            category, created = ServiceCategory.objects.get_or_create(
                salon=salon,
                slug=slug,
                defaults={"name": name, "display_order": order},
            )
            categories[slug] = category
            self.stdout.write(f"{'created' if created else 'exists'}: category {category.name}")

        for name, slug, category_slug, price, minutes, featured, order, description in SERVICES:
            service, created = Service.objects.get_or_create(
                salon=salon,
                slug=slug,
                defaults={
                    "name": name,
                    "category": categories[category_slug],
                    "description": description,
                    "price_paise": price,
                    "duration_minutes": minutes,
                    "is_featured": featured,
                    "display_order": order,
                },
            )
            state = "created" if created else "exists"
            self.stdout.write(f"{state}: service {service.name} ({service.price_paise} paise)")

        invalidate_services_cache()
        self.stdout.write(
            self.style.SUCCESS(
                f"catalog ready for {salon.name}: "
                f"{len(CATEGORIES)} categories, {len(SERVICES)} services"
            )
        )
