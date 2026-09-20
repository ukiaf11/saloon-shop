"""seed_catalog tests.

Seeds get re-run on every fresh environment and often against an existing one,
so idempotency is the property that matters -- and re-seeding must never move a
price behind the audit trail's back.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import Service, ServiceCategory, ServicePriceHistory
from apps.catalog.services import change_service_price

pytestmark = pytest.mark.django_db


def seed():
    out = StringIO()
    call_command("seed_catalog", stdout=out)
    return out.getvalue()


def test_requires_a_salon(db):
    with pytest.raises(CommandError, match="seed_salon"):
        seed()


def test_creates_the_catalogue(salon):
    seed()

    assert ServiceCategory.objects.count() == 3
    assert Service.objects.count() == 8

    prices = dict(Service.objects.values_list("slug", "price_paise"))
    assert prices == {
        "hair-cutting": 30000,
        "shaving": 15000,
        "face-massage": 40000,
        "hair-spa": 80000,
        "beard-trim": 12000,
        "head-massage": 35000,
        "hair-colour": 120000,
        "facial": 90000,
    }
    assert Service.objects.get(slug="hair-cutting").category.slug == "hair"
    assert Service.objects.get(slug="beard-trim").category.slug == "grooming"
    assert Service.objects.get(slug="facial").category.slug == "skin"


def test_is_idempotent(salon):
    seed()
    seed()

    assert ServiceCategory.objects.count() == 3
    assert Service.objects.count() == 8


def test_rerun_does_not_rewrite_an_edited_price(salon, owner):
    seed()
    service = Service.objects.get(slug="hair-cutting")
    change_service_price(service, 33000, changed_by=owner, reason="Owner revision")

    seed()

    assert Service.objects.get(slug="hair-cutting").price_paise == 33000
    assert ServicePriceHistory.objects.filter(service=service).count() == 1
