"""Fixtures for the UPI QR payment flow: a salon with a campaign, an owner who
can sign in, a QR on file, and a helper to place and claim orders."""

from __future__ import annotations

import datetime as dt
import io
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.models import AdminUser, Role
from apps.catalog.models import Service, ServiceCategory
from apps.orders.services import create_order
from apps.payments.models import PaymentSettings
from apps.promotions.models import CampaignConfig, DailyCampaign, RewardType
from apps.promotions.services import provision_campaign
from apps.salons.models import Salon
from common.crypto import encrypt

OWNER_PASSWORD = "a long owner passphrase 42"


@pytest.fixture(autouse=True)
def _fast_hashing(settings):
    # Argon2 is deliberately slow; tests only need a correct hash, not a costly one.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def salon(db) -> Salon:
    return Salon.objects.create(name="Test Salon", slug="test-salon")


@pytest.fixture
def config(salon) -> CampaignConfig:
    return CampaignConfig.objects.create(
        salon=salon,
        daily_capacity=40,
        lucky_count=5,
        discount_percent=10,
        min_distinct_services=2,
        max_entries_per_phone_per_day=1,
        reward_type=RewardType.SERVICE_PACKAGE,
        reward_definition={"service_slugs": ["hair-cutting", "shaving", "face-massage"]},
        effective_from=dt.date(2000, 1, 1),
    )


@pytest.fixture
def category(salon) -> ServiceCategory:
    return ServiceCategory.objects.create(salon=salon, name="Hair", slug="hair")


def _service(salon, category, name, slug, price_paise):
    return Service.objects.create(
        salon=salon,
        category=category,
        name=name,
        slug=slug,
        price_paise=price_paise,
        duration_minutes=30,
    )


@pytest.fixture
def haircut(salon, category) -> Service:
    return _service(salon, category, "Hair Cutting", "hair-cutting", 30000)


@pytest.fixture
def shaving(salon, category) -> Service:
    return _service(salon, category, "Shaving", "shaving", 15000)


@pytest.fixture
def face_massage(salon, category) -> Service:
    return _service(salon, category, "Face Massage", "face-massage", 40000)


@pytest.fixture
def hair_spa(salon, category) -> Service:
    return _service(salon, category, "Hair Spa", "hair-spa", 80000)


@pytest.fixture
def facial(salon, category) -> Service:
    return _service(salon, category, "Facial", "facial", 90000)


def _user(role, email):
    return AdminUser.objects.create_user(
        email=email, password=OWNER_PASSWORD, full_name=role.title(), role=role
    )


@pytest.fixture
def owner(db) -> AdminUser:
    return _user(Role.OWNER, "owner@test.example")


@pytest.fixture
def manager(db) -> AdminUser:
    return _user(Role.MANAGER, "manager@test.example")


def sign_in(client, email, password=OWNER_PASSWORD) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    return response.json()["token"]


@pytest.fixture
def owner_auth(client, owner) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {sign_in(client, owner.email)}"}


@pytest.fixture
def manager_auth(client, manager) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {sign_in(client, manager.email)}"}


def png_bytes(size=(300, 300), mode="RGB", colour="white") -> bytes:
    image = Image.new(mode, size, colour)
    # A few dark modules so the image is not a flat colour.
    for x in range(0, size[0], 20):
        for y in range(0, size[1], 20):
            image.putpixel((x, y), (0, 0, 0, 255) if mode == "RGBA" else (0, 0, 0))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def png_upload(name="qr.png", **kwargs) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, png_bytes(**kwargs), content_type="image/png")


@pytest.fixture
def qr_on_file(salon, owner) -> PaymentSettings:
    """A salon that takes UPI QR payments."""
    from apps.payments.services import update_payment_settings

    return update_payment_settings(
        salon, actor=owner, password=OWNER_PASSWORD, qr_file=png_upload(), upi_id="salon@okaxis"
    )


@pytest.fixture
def campaign(salon, config) -> DailyCampaign:
    return provision_campaign(salon)


def set_winning_positions(campaign: DailyCampaign, positions: list[int]) -> None:
    """Replace the drawn positions so a test knows which entries win."""
    DailyCampaign.objects.filter(pk=campaign.pk).update(
        encrypted_winning_positions=encrypt(json.dumps(positions))
    )


def place_order(salon, services, phone="9000000001", name="Rahul Sharma"):
    return create_order(
        salon,
        [{"service_id": str(s.id), "quantity": 1} for s in services],
        customer_name=name,
        customer_phone=phone,
    )


_next_reference = iter(range(100000000000, 999999999999))


def fresh_reference() -> str:
    return str(next(_next_reference))


def claim(client, order, reference=None):
    return client.post(
        f"/api/v1/orders/{order.id}/upi-payment",
        data=json.dumps({"reference": reference or fresh_reference()}),
        content_type="application/json",
    )
