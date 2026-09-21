"""The customer's side: "I have paid, here is my UPI reference"."""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone

from apps.orders.models import LuckySkipReason, Order
from apps.orders.state import OrderStatus
from apps.payments.models import Payment, PaymentStatus
from apps.promotions.models import CampaignConfig, DailyCampaign, ReservationStatus

from .conftest import claim, fresh_reference, place_order

pytestmark = pytest.mark.django_db


def test_a_claim_holds_a_draw_place_without_deciding_anything(
    client, salon, config, qr_on_file, haircut, shaving
):
    order = place_order(salon, [haircut, shaving])
    r = claim(client, order, "123456789012")
    assert r.status_code == 200, r.content
    body = r.json()

    assert body["status"] == OrderStatus.PAYMENT_PENDING
    assert body["paid_at"] is None
    assert body["payment"]["status"] == "awaiting_confirmation"
    assert body["payment"]["method"] == "upi_qr"
    assert body["payment"]["reference_last4"] == "9012"
    assert body["lucky"]["status"] == "held"
    assert body["lucky"]["participant_number"] is None

    payment = Payment.objects.get()
    assert payment.amount_paise == order.total_paise == 40500
    campaign = DailyCampaign.objects.get()
    assert campaign.paid_count == 0  # a claim is not a payment
    hold = order.slot_reservation
    assert hold.status == ReservationStatus.ACTIVE
    assert hold.expires_at > timezone.now() + dt.timedelta(hours=24)


def test_the_full_reference_is_never_echoed(client, salon, config, qr_on_file, haircut):
    order = place_order(salon, [haircut])
    r = claim(client, order, "123456789012")
    assert "123456789012" not in r.content.decode()
    assert "123456789012" not in client.get(f"/api/v1/orders/{order.id}").content.decode()


@pytest.mark.parametrize("reference", ["12345", "12345678901a", "1234567890123", ""])
def test_a_reference_must_be_twelve_digits(client, salon, config, qr_on_file, haircut, reference):
    order = place_order(salon, [haircut])
    r = (
        claim(client, order, reference)
        if reference
        else client.post(
            f"/api/v1/orders/{order.id}/upi-payment", data={}, content_type="application/json"
        )
    )
    assert r.status_code == 400
    assert not Payment.objects.exists()


def test_spaces_and_dashes_in_a_reference_are_forgiven(client, salon, config, qr_on_file, haircut):
    order = place_order(salon, [haircut])
    assert claim(client, order, "1234 5678-9012").status_code == 200
    assert Payment.objects.get().reference == "123456789012"


def test_no_qr_means_no_claims(client, salon, config, haircut):
    order = place_order(salon, [haircut])
    r = claim(client, order)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "upi_unavailable"


def test_an_unknown_order_is_not_found(client, salon, config, qr_on_file):
    r = client.post(
        "/api/v1/orders/00000000-0000-0000-0000-000000000000/upi-payment",
        data={"reference": "123456789012"},
        content_type="application/json",
    )
    assert r.status_code == 404


def test_one_upi_payment_cannot_back_two_orders(client, salon, config, qr_on_file, haircut):
    first = place_order(salon, [haircut], phone="9000000001")
    second = place_order(salon, [haircut], phone="9000000002")
    assert claim(client, first, "111122223333").status_code == 200

    r = claim(client, second, "111122223333")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "duplicate_reference"
    assert Order.objects.get(pk=second.pk).status == OrderStatus.DRAFT


def test_resubmitting_the_same_reference_is_harmless(client, salon, config, qr_on_file, haircut):
    order = place_order(salon, [haircut])
    assert claim(client, order, "111122223333").status_code == 200
    assert claim(client, order, "111122223333").status_code == 200
    assert Payment.objects.count() == 1


def test_a_typo_can_be_corrected_before_the_owner_decides(
    client, salon, config, qr_on_file, haircut
):
    order = place_order(salon, [haircut])
    claim(client, order, "111122223333")
    r = claim(client, order, "111122223334")
    assert r.status_code == 200
    assert Payment.objects.get().reference == "111122223334"
    assert r.json()["lucky"]["status"] == "held"


def test_one_draw_entry_per_phone_per_day(client, salon, config, qr_on_file, haircut):
    """A customer may buy twice; only the first order enters the draw."""
    first = place_order(salon, [haircut], phone="9000000001")
    second = place_order(salon, [haircut], phone="9000000001")
    assert claim(client, first).json()["lucky"]["status"] == "held"

    r = claim(client, second)
    assert r.status_code == 200  # the purchase itself is fine
    assert r.json()["lucky"] == {
        "status": "not_entered",
        "reason": LuckySkipReason.REPEAT_ENTRY,
        "participant_number": None,
        "campaign_date": None,
        "refund_paise": 0,
        "refund_status": None,
        "free_services": [],
    }


def test_a_full_day_takes_the_payment_but_not_the_entry(client, salon, config, qr_on_file, haircut):
    CampaignConfig.objects.filter(pk=config.pk).update(daily_capacity=1, lucky_count=1)
    first = place_order(salon, [haircut], phone="9000000001")
    second = place_order(salon, [haircut], phone="9000000002")
    assert claim(client, first).json()["lucky"]["status"] == "held"

    r = claim(client, second)
    assert r.status_code == 200
    assert r.json()["lucky"]["status"] == "not_entered"
    assert r.json()["lucky"]["reason"] == LuckySkipReason.DAY_FULL


def test_no_draw_configured_still_takes_the_payment(client, salon, qr_on_file, haircut):
    """No CampaignConfig at all. Orders need one to be priced, so this makes
    the order first and removes the config afterwards."""
    CampaignConfig.objects.create(
        salon=salon,
        daily_capacity=40,
        lucky_count=5,
        effective_from=dt.date(2000, 1, 1),
    )
    order = place_order(salon, [haircut])
    Order.objects.filter(pk=order.pk).update(campaign_config=None)
    CampaignConfig.objects.all().delete()

    r = claim(client, order)
    assert r.status_code == 200
    assert r.json()["lucky"]["reason"] == LuckySkipReason.NOT_RUNNING


def test_a_rejected_claim_can_be_made_again(client, salon, config, qr_on_file, haircut, owner):
    from apps.payments.services import reject_upi_payment

    order = place_order(salon, [haircut])
    claim(client, order, "111122223333")
    reject_upi_payment(Payment.objects.get().pk, actor=owner, reason="Not received")

    rejected = client.get(f"/api/v1/orders/{order.id}").json()
    assert rejected["status"] == OrderStatus.PAYMENT_FAILED
    assert rejected["payment"]["status"] == "rejected"
    assert rejected["payment"]["rejection_reason"] == "Not received"
    assert rejected["lucky"]["status"] == "pending"

    # The rejected reference is free again, e.g. the customer typed it right
    # the first time and the owner looked in the wrong place.
    again = claim(client, order, "111122223333")
    assert again.status_code == 200
    assert again.json()["payment"]["status"] == "awaiting_confirmation"
    assert again.json()["lucky"]["status"] == "held"
    assert Payment.objects.filter(status=PaymentStatus.AWAITING_CONFIRMATION).count() == 1


def test_a_paid_order_cannot_be_claimed_again(client, salon, config, qr_on_file, haircut, owner):
    from apps.payments.services import confirm_upi_payment

    order = place_order(salon, [haircut])
    claim(client, order)
    confirm_upi_payment(Payment.objects.get().pk, actor=owner)

    r = claim(client, order, fresh_reference())
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "order_not_payable"
