"""The owner/manager catalogue endpoints: price changes and service edits.

The money rule under test: a price can only change through the audited path,
so every change here must leave a ServicePriceHistory row, an AuditLog row,
and a fresh public /services payload.
"""

from __future__ import annotations

import json

import pytest

from apps.accounts.models import AdminUser, Role
from apps.audit.models import AuditLog
from apps.catalog.models import Service, ServicePriceHistory

pytestmark = pytest.mark.django_db

PASSWORD = "a long owner passphrase 42"
LIST_URL = "/api/v1/owner/services"


@pytest.fixture(autouse=True)
def _fast_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


def _staff(role: Role, email: str) -> AdminUser:
    return AdminUser.objects.create_user(
        email=email, password=PASSWORD, full_name=role.title(), role=role
    )


def _auth(client, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data=json.dumps({"email": email, "password": PASSWORD}),
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    return {"HTTP_AUTHORIZATION": f"Bearer {response.json()['token']}"}


@pytest.fixture
def boss_auth(client, db):
    _staff(Role.OWNER, "boss@test.example")
    return _auth(client, "boss@test.example")


@pytest.fixture
def manager_auth(client, db):
    _staff(Role.MANAGER, "manager@test.example")
    return _auth(client, "manager@test.example")


@pytest.fixture
def receptionist_auth(client, db):
    _staff(Role.RECEPTIONIST, "desk@test.example")
    return _auth(client, "desk@test.example")


@pytest.fixture
def retired(salon, hair_category):
    return Service.objects.create(
        salon=salon,
        category=hair_category,
        name="Retired Perm",
        slug="retired-perm",
        price_paise=50000,
        is_active=False,
        display_order=9,
    )


def set_price(client, auth, service, paise, reason=None):
    body = {"price_paise": paise}
    if reason is not None:
        body["reason"] = reason
    return client.post(
        f"{LIST_URL}/{service.id}/price",
        data=json.dumps(body),
        content_type="application/json",
        **auth,
    )


def patch_service(client, auth, service, **fields):
    return client.patch(
        f"{LIST_URL}/{service.id}",
        data=json.dumps(fields),
        content_type="application/json",
        **auth,
    )


# --- listing -----------------------------------------------------------------


def test_the_list_shows_every_service_including_hidden_ones(client, boss_auth, haircut, retired):
    r = client.get(LIST_URL, **boss_auth)
    assert r.status_code == 200
    rows = {row["slug"]: row for row in r.json()["results"]}
    assert set(rows) == {"hair-cutting", "retired-perm"}
    assert rows["retired-perm"]["is_active"] is False
    assert rows["hair-cutting"] == {
        "id": str(haircut.id),
        "name": "Hair Cutting",
        "slug": "hair-cutting",
        "description": "Precision cut and styling.",
        "category": {"id": str(haircut.category_id), "name": "Hair"},
        "price_paise": 30000,
        "duration_minutes": 30,
        "is_active": True,
        "is_featured": True,
        "display_order": 1,
        "image_url": None,
        "updated_at": rows["hair-cutting"]["updated_at"],
        "price_history": [],
    }


def test_the_management_list_is_never_publicly_readable(client, haircut):
    assert client.get(LIST_URL).status_code == 401


def test_a_receptionist_cannot_manage_the_catalogue(client, receptionist_auth, haircut):
    assert client.get(LIST_URL, **receptionist_auth).status_code == 403
    assert set_price(client, receptionist_auth, haircut, 40000).status_code == 403
    haircut.refresh_from_db()
    assert haircut.price_paise == 30000


# --- price change --------------------------------------------------------------


def test_a_price_change_writes_history_audit_and_the_new_public_price(client, boss_auth, haircut):
    # Warm the public cache so the test proves invalidation, not a cold read.
    assert client.get("/api/v1/services").json()["results"][0]["price_paise"] == 30000

    r = set_price(client, boss_auth, haircut, 35000, reason="Festival pricing")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["price_paise"] == 35000
    assert body["price_history"][0]["old_price_paise"] == 30000
    assert body["price_history"][0]["new_price_paise"] == 35000
    assert body["price_history"][0]["changed_by"] == "boss@test.example"
    assert body["price_history"][0]["reason"] == "Festival pricing"

    history = ServicePriceHistory.objects.get()
    assert (history.old_price_paise, history.new_price_paise) == (30000, 35000)

    entry = AuditLog.objects.get(action="service.price_changed")
    assert entry.before == {"price_paise": 30000}
    assert entry.after == {"price_paise": 35000, "reason": "Festival pricing"}

    # The very next public read sees the new price -- no TTL wait.
    assert client.get("/api/v1/services").json()["results"][0]["price_paise"] == 35000


def test_a_manager_may_change_prices(client, manager_auth, haircut):
    assert set_price(client, manager_auth, haircut, 32000).status_code == 200
    assert ServicePriceHistory.objects.get().changed_by.email == "manager@test.example"


def test_the_same_price_is_rejected_rather_than_silently_ignored(client, boss_auth, haircut):
    r = set_price(client, boss_auth, haircut, 30000)
    assert r.status_code == 400
    assert "already the price" in r.json()["error"]["message"]
    assert not ServicePriceHistory.objects.exists()


@pytest.mark.parametrize("bad", [0, -100, 99, 50_000_001, "300.50"])
def test_out_of_range_or_non_integer_prices_are_rejected(client, boss_auth, haircut, bad):
    r = set_price(client, boss_auth, haircut, bad)
    assert r.status_code == 400
    haircut.refresh_from_db()
    assert haircut.price_paise == 30000
    assert not ServicePriceHistory.objects.exists()


def test_an_unknown_service_is_not_found(client, boss_auth):
    r = client.post(
        f"{LIST_URL}/00000000-0000-0000-0000-000000000000/price",
        data=json.dumps({"price_paise": 30000}),
        content_type="application/json",
        **boss_auth,
    )
    assert r.status_code == 404


def test_successive_changes_keep_the_newest_history_first(client, boss_auth, haircut):
    set_price(client, boss_auth, haircut, 35000)
    r = set_price(client, boss_auth, haircut, 32000)
    pairs = [(h["old_price_paise"], h["new_price_paise"]) for h in r.json()["price_history"]]
    assert pairs == [(35000, 32000), (30000, 35000)]


# --- non-price edits -------------------------------------------------------------


def test_hiding_a_service_removes_it_from_the_public_site(client, boss_auth, haircut):
    assert client.get("/api/v1/services").json()["results"] != []

    r = patch_service(client, boss_auth, haircut, is_active=False)
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    assert client.get("/api/v1/services").json()["results"] == []

    entry = AuditLog.objects.get(action="service.updated")
    assert entry.before == {"is_active": True}
    assert entry.after == {"is_active": False}


def test_duration_and_featured_can_change_together(client, manager_auth, haircut):
    r = patch_service(client, manager_auth, haircut, duration_minutes=45, is_featured=False)
    assert r.status_code == 200
    haircut.refresh_from_db()
    assert (haircut.duration_minutes, haircut.is_featured) == (45, False)


def test_patch_cannot_smuggle_a_price_past_the_history(client, boss_auth, haircut):
    r = patch_service(client, boss_auth, haircut, price_paise=1)
    # Unknown fields are ignored by the serializer; with nothing else present
    # the request has nothing to change.
    assert r.status_code == 400
    haircut.refresh_from_db()
    assert haircut.price_paise == 30000
    assert not ServicePriceHistory.objects.exists()


@pytest.mark.parametrize("minutes", [0, 4, 481])
def test_unreasonable_durations_are_rejected(client, boss_auth, haircut, minutes):
    assert patch_service(client, boss_auth, haircut, duration_minutes=minutes).status_code == 400


def test_an_unchanged_patch_writes_no_audit_noise(client, boss_auth, haircut):
    r = patch_service(client, boss_auth, haircut, is_featured=True)  # already true
    assert r.status_code == 200
    assert not AuditLog.objects.filter(action="service.updated").exists()
