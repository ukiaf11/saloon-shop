"""HTTP-level behaviour of the quote and order endpoints."""

from __future__ import annotations

import json

import pytest

from apps.orders.models import Order

pytestmark = [pytest.mark.django_db, pytest.mark.urls("apps.orders.tests.urls")]


@pytest.fixture(autouse=True)
def _one_active_salon(salon):
    """The views resolve the single active salon themselves."""
    return salon


def post(client, path, payload, **extra):
    return client.post(path, data=json.dumps(payload), content_type="application/json", **extra)


def body(response):
    return json.loads(response.content)


# --- quote ----------------------------------------------------------------


def test_quote_returns_the_contract_shape(client, config, haircut, shaving):
    r = post(
        client,
        "/orders/quote",
        {
            "items": [
                {"service_id": str(haircut.id), "quantity": 1},
                {"service_id": str(shaving.id), "quantity": 1},
            ]
        },
    )
    assert r.status_code == 200
    d = body(r)

    assert set(d) == {
        "currency",
        "subtotal_paise",
        "discount_percent",
        "configured_discount_percent",
        "discount_paise",
        "payable_paise",
        "eligible_for_discount",
        "distinct_service_count",
        "min_distinct_services",
        "expires_at",
        "lines",
    }
    assert d["currency"] == "INR"
    assert d["payable_paise"] == 40500
    assert d["eligible_for_discount"] is True
    assert len(d["lines"]) == 2
    assert set(d["lines"][0]) == {
        "service_id",
        "name",
        "unit_price_paise",
        "quantity",
        "line_total_paise",
        "discount_alloc_paise",
        "net_paid_paise",
    }


def test_quote_requires_no_authentication(client, config, haircut):
    r = post(client, "/orders/quote", {"items": [{"service_id": str(haircut.id)}]})
    assert r.status_code == 200


def test_quote_rejects_an_empty_basket(client, config):
    r = post(client, "/orders/quote", {"items": []})
    assert r.status_code == 400
    assert body(r)["error"]["code"] == "validation_failed"


def test_quote_rejects_an_unknown_service(client, config):
    import uuid

    r = post(client, "/orders/quote", {"items": [{"service_id": str(uuid.uuid4())}]})
    assert r.status_code == 400
    assert body(r)["error"]["code"] == "service_unavailable_for_order"


def test_quote_writes_nothing(client, config, haircut, shaving):
    post(
        client,
        "/orders/quote",
        {"items": [{"service_id": str(haircut.id)}, {"service_id": str(shaving.id)}]},
    )
    assert Order.objects.count() == 0


# --- create ---------------------------------------------------------------


def test_create_returns_201_and_the_contract_shape(client, config, haircut, shaving):
    r = post(
        client,
        "/orders",
        {
            "items": [{"service_id": str(haircut.id)}, {"service_id": str(shaving.id)}],
            "customer": {"name": "Rahul Sharma", "phone": "9000000000"},
        },
    )
    assert r.status_code == 201
    d = body(r)

    assert set(d) == {
        "id",
        "public_order_number",
        "status",
        "currency",
        "subtotal_paise",
        "discount_percent_applied",
        "discount_paise",
        "total_paise",
        "created_at",
        "customer",
        "items",
    }
    assert d["status"] == "DRAFT"
    assert d["total_paise"] == 40500


def test_create_never_echoes_the_full_phone_number(client, config, haircut, shaving):
    r = post(
        client,
        "/orders",
        {
            "items": [{"service_id": str(haircut.id)}, {"service_id": str(shaving.id)}],
            "customer": {"name": "Rahul", "phone": "9000000000"},
        },
    )
    raw = r.content.decode()
    assert "9000000000" not in raw
    assert "+919000000000" not in raw
    assert body(r)["customer"]["phone_masked"].endswith("0000")


def test_create_ignores_a_forged_price_over_http(client, config, haircut, shaving):
    """The exit gate, exercised through the real request path."""
    r = post(
        client,
        "/orders",
        {
            "items": [
                {"service_id": str(haircut.id), "quantity": 1, "price_paise": 1},
                {"service_id": str(shaving.id), "quantity": 1, "unit_price_paise": 0},
            ],
            "customer": {"name": "Rahul", "phone": "9000000000"},
            "total_paise": 1,
            "discount_paise": 999999,
            "status": "PAID",
        },
    )
    assert r.status_code == 201
    d = body(r)
    assert d["total_paise"] == 40500
    assert d["discount_paise"] == 4500
    assert d["status"] == "DRAFT"


def test_create_rejects_a_missing_customer(client, config, haircut):
    r = post(client, "/orders", {"items": [{"service_id": str(haircut.id)}]})
    assert r.status_code == 400


def test_idempotency_header_prevents_a_duplicate_order(client, config, haircut, shaving):
    payload = {
        "items": [{"service_id": str(haircut.id)}, {"service_id": str(shaving.id)}],
        "customer": {"name": "Rahul", "phone": "9000000000"},
    }
    a = post(client, "/orders", payload, HTTP_IDEMPOTENCY_KEY="abc-123")
    b = post(client, "/orders", payload, HTTP_IDEMPOTENCY_KEY="abc-123")

    assert body(a)["id"] == body(b)["id"]
    assert Order.objects.count() == 1


# --- detail ---------------------------------------------------------------


def test_detail_round_trips(client, config, haircut, shaving):
    created = body(
        post(
            client,
            "/orders",
            {
                "items": [
                    {"service_id": str(haircut.id)},
                    {"service_id": str(shaving.id)},
                ],
                "customer": {"name": "Rahul", "phone": "9000000000"},
            },
        )
    )
    r = client.get(f"/orders/{created['id']}")
    assert r.status_code == 200
    assert body(r)["public_order_number"] == created["public_order_number"]


def test_detail_404s_for_an_unknown_id(client, config):
    import uuid

    r = client.get(f"/orders/{uuid.uuid4()}")
    assert r.status_code == 404
    assert body(r)["error"]["code"] == "not_found"
