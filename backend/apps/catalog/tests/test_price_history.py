"""Price-history tests.

REQUIREMENTS.md 2.2 makes the history row mandatory. These tests are the thing
that fails when someone later "simplifies" the guard away.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache

from apps.catalog.models import PriceChangeNotAudited, Service, ServicePriceHistory
from apps.catalog.services import change_service_price, create_service, update_service
from common.cache import KEY_SERVICES
from common.exceptions import ValidationFailed

pytestmark = pytest.mark.django_db


def test_price_change_writes_history(haircut, owner):
    updated = change_service_price(haircut, 35000, changed_by=owner, reason="Diwali revision")

    assert updated.price_paise == 35000
    haircut.refresh_from_db()
    assert haircut.price_paise == 35000

    entry = ServicePriceHistory.objects.get(service=haircut)
    assert entry.old_price_paise == 30000
    assert entry.new_price_paise == 35000
    assert entry.changed_by == owner
    assert entry.reason == "Diwali revision"


def test_unchanged_price_writes_no_history(haircut, owner):
    change_service_price(haircut, 30000, changed_by=owner, reason="no-op")

    assert not ServicePriceHistory.objects.filter(service=haircut).exists()


def test_successive_changes_chain(haircut, owner):
    change_service_price(haircut, 35000, changed_by=owner)
    change_service_price(haircut, 32000, changed_by=owner)

    # Compared as a set: two inserts in the same test can land on the same
    # microsecond, and the chain is provable from the pairs alone.
    entries = set(
        ServicePriceHistory.objects.filter(service=haircut).values_list(
            "old_price_paise", "new_price_paise"
        )
    )
    assert entries == {(30000, 35000), (35000, 32000)}
    assert Service.objects.get(pk=haircut.pk).price_paise == 32000


def test_direct_save_of_a_new_price_is_blocked(haircut):
    """The whole point of the guard: an unaudited price change must not land."""
    loaded = Service.objects.get(pk=haircut.pk)
    loaded.price_paise = 1

    with pytest.raises(PriceChangeNotAudited):
        loaded.save()

    assert Service.objects.get(pk=haircut.pk).price_paise == 30000
    assert not ServicePriceHistory.objects.exists()


def test_authorisation_does_not_survive_the_save(haircut, owner):
    """One sanctioned save, not a permanently unlocked instance."""
    service = change_service_price(haircut, 35000, changed_by=owner)

    service.price_paise = 40000
    with pytest.raises(PriceChangeNotAudited):
        service.save()


def test_saving_other_fields_is_not_blocked(haircut):
    loaded = Service.objects.get(pk=haircut.pk)
    loaded.name = "Haircut"
    loaded.is_featured = False
    loaded.save()

    loaded.refresh_from_db()
    assert loaded.name == "Haircut"
    assert loaded.price_paise == 30000


def test_creating_a_service_is_not_blocked(salon):
    service = create_service(salon=salon, name="Beard Trim", price_paise=12000)

    assert service.slug == "beard-trim"
    assert service.price_paise == 12000
    assert not ServicePriceHistory.objects.exists()


def test_price_change_invalidates_the_services_cache(haircut, owner):
    cache.set(KEY_SERVICES, {"categories": [], "results": []})

    change_service_price(haircut, 35000, changed_by=owner)

    assert cache.get(KEY_SERVICES) is None


def test_update_service_routes_price_through_the_audited_path(haircut, owner):
    updated = update_service(
        haircut,
        changed_by=owner,
        price_reason="Seasonal",
        name="Hair Cutting (Deluxe)",
        price_paise=45000,
    )

    assert updated.name == "Hair Cutting (Deluxe)"
    assert updated.price_paise == 45000
    entry = ServicePriceHistory.objects.get(service=haircut)
    assert entry.new_price_paise == 45000
    assert entry.reason == "Seasonal"


@pytest.mark.parametrize("bad_price", [-1, 350.0, "35000", True])
def test_non_integer_paise_is_rejected(haircut, bad_price):
    """Money is integer paise. A float or a rupee string never reaches the DB."""
    with pytest.raises(ValidationFailed):
        change_service_price(haircut, bad_price)
