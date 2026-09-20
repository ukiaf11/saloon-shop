"""GET /services contract tests.

The frontend validates this payload with a Zod schema, so a field that changes
name or type here breaks the page rather than degrading it.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.catalog.models import Service, ServiceCategory
from apps.catalog.services import change_service_price

pytestmark = [pytest.mark.django_db, pytest.mark.urls("apps.catalog.tests.urls")]

SERVICE_FIELDS = {
    "id",
    "name",
    "slug",
    "description",
    "price_paise",
    "duration_minutes",
    "image_url",
    "is_featured",
    "display_order",
    "category",
}


@pytest.fixture
def catalogue(salon, hair_category, haircut):
    """One salon with the interesting cases: uncategorised, inactive service,
    inactive category, and a service under that inactive category."""
    grooming = ServiceCategory.objects.create(
        salon=salon, name="Grooming", slug="grooming", display_order=2
    )
    retired = ServiceCategory.objects.create(
        salon=salon, name="Retired", slug="retired", display_order=3, is_active=False
    )
    Service.objects.create(
        salon=salon,
        category=grooming,
        name="Shaving",
        slug="shaving",
        price_paise=15000,
        duration_minutes=20,
        display_order=2,
    )
    Service.objects.create(
        salon=salon,
        category=None,
        name="Head Massage",
        slug="head-massage",
        price_paise=35000,
        display_order=3,
    )
    Service.objects.create(
        salon=salon,
        category=retired,
        name="Old Package",
        slug="old-package",
        price_paise=50000,
        display_order=4,
    )
    Service.objects.create(
        salon=salon,
        name="Discontinued",
        slug="discontinued",
        price_paise=9900,
        display_order=5,
        is_active=False,
    )
    return salon


def get_services(client):
    response = client.get(reverse("services"), headers={"accept": "application/json"})
    assert response.status_code == 200
    return response.json()


def test_payload_shape_matches_the_contract(client, catalogue):
    payload = get_services(client)

    assert set(payload) == {"categories", "results"}
    # Not paginated -- no count/next/previous envelope.
    assert "count" not in payload

    cutting = next(item for item in payload["results"] if item["slug"] == "hair-cutting")
    assert set(cutting) == SERVICE_FIELDS
    assert cutting["price_paise"] == 30000
    assert isinstance(cutting["price_paise"], int)
    assert cutting["duration_minutes"] == 30
    assert cutting["is_featured"] is True
    assert cutting["image_url"] is None
    assert cutting["category"] == {
        "id": str(catalogue.service_categories.get(slug="hair").id),
        "name": "Hair",
        "slug": "hair",
    }

    hair = next(item for item in payload["categories"] if item["slug"] == "hair")
    assert set(hair) == {"id", "name", "slug", "display_order"}


def test_internal_fields_are_never_exposed(client, catalogue):
    payload = get_services(client)

    for item in payload["results"]:
        assert "is_active" not in item
        assert "price_history" not in item
        assert "salon" not in item


def test_inactive_services_and_categories_are_excluded(client, catalogue):
    payload = get_services(client)

    assert "discontinued" not in {item["slug"] for item in payload["results"]}
    assert "retired" not in {item["slug"] for item in payload["categories"]}


def test_service_under_an_inactive_category_reports_no_category(client, catalogue):
    """Its category id is not in `categories`, so returning it would hand the
    frontend an unresolvable filter value."""
    payload = get_services(client)

    old_package = next(item for item in payload["results"] if item["slug"] == "old-package")
    assert old_package["category"] is None


def test_uncategorised_service_reports_no_category(client, catalogue):
    payload = get_services(client)

    massage = next(item for item in payload["results"] if item["slug"] == "head-massage")
    assert massage["category"] is None


def test_ordering_is_display_order_then_name(client, salon):
    Service.objects.create(salon=salon, name="Zeta", slug="zeta", price_paise=100, display_order=1)
    Service.objects.create(
        salon=salon, name="Alpha", slug="alpha", price_paise=100, display_order=1
    )
    Service.objects.create(
        salon=salon, name="Aaa Last", slug="aaa-last", price_paise=100, display_order=2
    )

    payload = get_services(client)

    assert [item["slug"] for item in payload["results"]] == ["alpha", "zeta", "aaa-last"]


def test_image_url_is_absolute(client, haircut):
    # Assign the stored name directly: the test needs a URL, not a real upload.
    Service.objects.filter(pk=haircut.pk).update(image="catalog/services/hair-cutting.webp")

    payload = get_services(client)

    cutting = next(item for item in payload["results"] if item["slug"] == "hair-cutting")
    assert cutting["image_url"].startswith("http://testserver/")
    assert cutting["image_url"].endswith("/catalog/services/hair-cutting.webp")


def test_a_price_change_is_visible_on_the_next_request(client, haircut, owner):
    """The cached payload must not outlive the price it quotes."""
    assert get_services(client)["results"][0]["price_paise"] == 30000

    change_service_price(haircut, 35000, changed_by=owner, reason="Revision")

    assert get_services(client)["results"][0]["price_paise"] == 35000


def test_endpoint_is_public(client, catalogue):
    """The project default is IsAuthenticated; this endpoint opts out."""
    response = client.get(reverse("services"), headers={"accept": "application/json"})

    assert response.status_code == 200
