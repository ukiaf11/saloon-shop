"""The owner's side: confirming or rejecting a claim, and what that decides.

Confirmation is the lucky decision transaction of Doc 2 section 16, with the
owner's check standing in for the gateway's verification.
"""

from __future__ import annotations

import datetime as dt
import json
import threading

import pytest
from django.db import connections

from apps.audit.models import AuditLog
from apps.orders.models import LuckySkipReason, Order
from apps.orders.state import OrderStatus
from apps.payments.models import Payment, PaymentStatus
from apps.payments.services import (
    PaymentAlreadyDecided,
    confirm_upi_payment,
    submit_upi_claim,
)
from apps.promotions.models import DailyCampaign, LuckyDecision, ReservationStatus
from apps.refunds.models import Refund, RefundStatus

from .conftest import claim, fresh_reference, place_order, set_winning_positions

pytestmark = pytest.mark.django_db


def post(client, path, auth, payload=None):
    return client.post(
        path, data=json.dumps(payload or {}), content_type="application/json", **auth
    )


def confirm(client, auth, payment, reference=None):
    """Confirm as the panel does: naming the reference the owner checked."""
    if reference is None:
        payment.refresh_from_db()
        reference = payment.reference
    return post(
        client, f"/api/v1/owner/payments/{payment.id}/confirm", auth, {"reference": reference}
    )


def claimed(client, salon, services, phone):
    order = place_order(salon, services, phone=phone)
    assert claim(client, order).status_code == 200
    return order, Payment.objects.get(order=order)


def test_confirming_marks_the_order_paid_and_gives_it_a_draw_number(
    client, salon, campaign, qr_on_file, owner_auth, haircut, shaving
):
    set_winning_positions(campaign, [5])
    order, payment = claimed(client, salon, [haircut, shaving], "9000000001")

    r = confirm(client, owner_auth, payment)
    assert r.status_code == 200, r.content
    assert r.json()["status"] == "confirmed"
    assert r.json()["draw"]["status"] == "not_won"
    assert r.json()["draw"]["participant_number"] == 1

    order.refresh_from_db()
    assert order.status == OrderStatus.LUCKY_DECIDED
    assert order.paid_at is not None
    campaign.refresh_from_db()
    assert (campaign.paid_count, campaign.winner_count) == (1, 0)
    assert order.slot_reservation.status == ReservationStatus.CONSUMED

    entry = AuditLog.objects.get(action="payment.confirmed")
    assert entry.actor_email == "owner@test.example"
    assert entry.after["participant_number"] == 1
    assert entry.after["is_winner"] is False


def test_draw_numbers_follow_confirmation_order(
    client, salon, campaign, qr_on_file, owner_auth, haircut
):
    set_winning_positions(campaign, [40])
    claims = [claimed(client, salon, [haircut], f"900000000{i}") for i in range(3)]
    # Confirmed in reverse: the number is the position in the day's paid
    # sequence, which is when the money was verified, not when it was claimed.
    for _, payment in reversed(claims):
        confirm(client, owner_auth, payment)

    numbers = {
        order.public_order_number: order.lucky_decision.participant_number
        for order, _ in ((Order.objects.get(pk=o.pk), p) for o, p in claims)
    }
    assert sorted(numbers.values()) == [1, 2, 3]
    assert Order.objects.get(pk=claims[2][0].pk).lucky_decision.participant_number == 1


def test_a_winner_is_refunded_only_what_the_reward_covers(
    client, salon, campaign, qr_on_file, owner_auth, haircut, hair_spa, shaving, face_massage
):
    """REQUIREMENTS.md 8.1's worked example: Haircut 300 + Hair Spa 800, 10%
    off. Haircut is in the package, so its net paid (270) comes back; Hair Spa
    is not, so it stays paid; Shaving and Face Massage become free."""
    set_winning_positions(campaign, [1])
    order, payment = claimed(client, salon, [haircut, hair_spa], "9000000001")
    assert order.total_paise == 99000

    r = confirm(client, owner_auth, payment)
    assert r.status_code == 200
    draw = r.json()["draw"]
    assert draw["status"] == "won"
    assert draw["refund_paise"] == 27000
    assert draw["refund_status"] == "pending"
    assert draw["free_services"] == ["Shaving", "Face Massage"]

    refund = Refund.objects.get()
    assert (refund.amount_paise, refund.status, refund.payment_id) == (
        27000,
        RefundStatus.PENDING,
        payment.id,
    )
    order.refresh_from_db()
    assert order.status == OrderStatus.REFUND_PENDING
    campaign.refresh_from_db()
    assert campaign.winner_count == 1

    customer_view = client.get(f"/api/v1/orders/{order.id}").json()["lucky"]
    assert customer_view["status"] == "won"
    assert customer_view["refund_paise"] == 27000


def test_a_winner_who_bought_nothing_in_the_package_gets_it_all_free(
    client, salon, campaign, qr_on_file, owner_auth, hair_spa, haircut, shaving, face_massage
):
    set_winning_positions(campaign, [1])
    order, payment = claimed(client, salon, [hair_spa], "9000000001")
    confirm(client, owner_auth, payment)

    decision = LuckyDecision.objects.get()
    assert decision.is_winner and decision.reward_refund_paise == 0
    assert decision.free_services == ["Hair Cutting", "Shaving", "Face Massage"]
    assert not Refund.objects.exists()
    assert Order.objects.get(pk=order.pk).status == OrderStatus.LUCKY_DECIDED


def test_a_payment_is_decided_once(client, salon, campaign, qr_on_file, owner_auth, haircut):
    _, payment = claimed(client, salon, [haircut], "9000000001")
    assert confirm(client, owner_auth, payment).status_code == 200
    again = confirm(client, owner_auth, payment)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "payment_already_decided"
    assert DailyCampaign.objects.get().paid_count == 1


def test_rejecting_frees_the_hold_and_blocks_confirmation(
    client, salon, campaign, qr_on_file, owner_auth, haircut
):
    order, payment = claimed(client, salon, [haircut], "9000000001")
    r = post(
        client,
        f"/api/v1/owner/payments/{payment.id}/reject",
        owner_auth,
        {"reason": "No such payment in my account", "reference": payment.reference},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"

    order.refresh_from_db()
    assert order.status == OrderStatus.PAYMENT_FAILED
    assert order.slot_reservation.status == ReservationStatus.CANCELLED
    assert confirm(client, owner_auth, payment).status_code == 409
    assert AuditLog.objects.filter(action="payment.rejected").count() == 1


def test_a_claim_confirmed_after_its_day_ended_is_paid_but_not_entered(
    client, salon, campaign, qr_on_file, owner_auth, haircut
):
    """Paid at 23:50, confirmed at 00:10: the money is real, but that day's
    draw has ended -- even if the nightly close has not run yet."""
    order, payment = claimed(client, salon, [haircut], "9000000001")
    DailyCampaign.objects.filter(pk=campaign.pk).update(
        campaign_date=campaign.campaign_date - dt.timedelta(days=1)
    )

    r = confirm(client, owner_auth, payment)
    assert r.status_code == 200
    assert r.json()["draw"]["status"] == "not_entered"
    assert r.json()["draw"]["reason"] == LuckySkipReason.DAY_CLOSED

    order.refresh_from_db()
    assert order.status == OrderStatus.PAID
    assert DailyCampaign.objects.get().paid_count == 0


def test_the_owner_is_warned_about_a_claim_from_an_ended_day(
    client, salon, campaign, qr_on_file, owner_auth, haircut
):
    claimed(client, salon, [haircut], "9000000001")
    listed = client.get("/api/v1/owner/payments", **owner_auth).json()["results"]
    assert listed[0]["draw_day_over"] is False

    DailyCampaign.objects.filter(pk=campaign.pk).update(
        campaign_date=campaign.campaign_date - dt.timedelta(days=1)
    )
    listed = client.get("/api/v1/owner/payments", **owner_auth).json()["results"]
    assert listed[0]["draw_day_over"] is True


def test_a_repeat_entry_is_paid_but_takes_no_number(
    client, salon, campaign, qr_on_file, owner_auth, haircut
):
    _, first = claimed(client, salon, [haircut], "9000000001")
    second_order, second = claimed(client, salon, [haircut], "9000000001")
    confirm(client, owner_auth, first)
    r = confirm(client, owner_auth, second)

    assert r.json()["draw"]["reason"] == LuckySkipReason.REPEAT_ENTRY
    assert Order.objects.get(pk=second_order.pk).status == OrderStatus.PAID
    assert DailyCampaign.objects.get().paid_count == 1


def test_the_owner_list_shows_everything_needed_to_check_the_money(
    client, salon, campaign, qr_on_file, owner_auth, haircut, shaving
):
    order, payment = claimed(client, salon, [haircut, shaving], "9876543210")
    listed = client.get("/api/v1/owner/payments", **owner_auth).json()["results"]
    assert len(listed) == 1
    row = listed[0]
    assert row["reference"] == payment.reference
    assert row["amount_paise"] == 40500
    assert row["customer"] == {"name": "Rahul Sharma", "phone": order.customer.phone}
    assert [i["name"] for i in row["order"]["items"]] == ["Hair Cutting", "Shaving"]
    assert row["draw"]["status"] == "held"

    assert client.get("/api/v1/owner/payments?status=confirmed", **owner_auth).json() == {
        "results": []
    }
    assert client.get("/api/v1/owner/payments?status=bogus", **owner_auth).status_code == 400


def test_only_the_owner_decides_payments(
    client, salon, campaign, qr_on_file, manager_auth, haircut
):
    _, payment = claimed(client, salon, [haircut], "9000000001")
    assert confirm(client, manager_auth, payment).status_code == 403
    assert client.post(f"/api/v1/owner/payments/{payment.id}/confirm").status_code == 401
    assert Payment.objects.get().status == PaymentStatus.AWAITING_CONFIRMATION


# --- refunds -------------------------------------------------------------------


@pytest.fixture
def pending_refund(client, salon, campaign, qr_on_file, owner_auth, haircut, hair_spa):
    set_winning_positions(campaign, [1])
    _, payment = claimed(client, salon, [haircut, hair_spa], "9000000001")
    confirm(client, owner_auth, payment)
    return Refund.objects.get()


def mark_sent(client, auth, refund, **payload):
    return post(client, f"/api/v1/owner/refunds/{refund.id}/mark-sent", auth, payload)


def test_the_owner_sees_refunds_to_send(client, owner_auth, pending_refund):
    listed = client.get("/api/v1/owner/refunds", **owner_auth).json()["results"]
    assert len(listed) == 1
    assert listed[0]["amount_paise"] == 27000
    assert listed[0]["participant_number"] == 1
    assert len(listed[0]["payment_reference"]) == 12


def test_marking_a_refund_sent_by_upi(client, owner_auth, pending_refund):
    r = mark_sent(client, owner_auth, pending_refund, method="UPI", reference="5555 6666 7777")
    assert r.status_code == 200, r.content
    assert r.json()["status"] == "sent"
    assert r.json()["reference"] == "555566667777"

    order = pending_refund.order
    order.refresh_from_db()
    assert order.status == OrderStatus.REFUNDED
    customer_view = client.get(f"/api/v1/orders/{order.id}").json()["lucky"]
    assert customer_view["refund_status"] == "sent"
    assert AuditLog.objects.filter(action="refund.sent").count() == 1

    again = mark_sent(client, owner_auth, pending_refund, method="CASH")
    assert again.status_code == 409


def test_a_upi_refund_needs_its_reference(client, owner_auth, pending_refund):
    assert mark_sent(client, owner_auth, pending_refund, method="UPI").status_code == 400
    assert (
        mark_sent(client, owner_auth, pending_refund, method="UPI", reference="12").status_code
        == 400
    )
    pending_refund.refresh_from_db()
    assert pending_refund.status == RefundStatus.PENDING


def test_a_cash_refund_needs_no_reference(client, owner_auth, pending_refund):
    r = mark_sent(client, owner_auth, pending_refund, method="CASH", reference="ignored")
    assert r.status_code == 200
    assert r.json()["method"] == "CASH"
    assert r.json()["reference"] is None


def test_only_the_owner_marks_refunds(client, manager_auth, pending_refund):
    assert mark_sent(client, manager_auth, pending_refund, method="CASH").status_code == 403


# --- races ----------------------------------------------------------------------


def _run_together(n, work):
    barrier = threading.Barrier(n)
    results, lock = [], threading.Lock()

    def attempt(i):
        try:
            barrier.wait(timeout=20)
            outcome = work(i)
        except Exception as exc:  # recorded, asserted on below
            outcome = exc
        finally:
            connections.close_all()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_simultaneous_confirmations_get_distinct_consecutive_numbers(
    salon, campaign, qr_on_file, owner, haircut
):
    orders = [place_order(salon, [haircut], phone=f"90000001{i:02d}") for i in range(10)]
    for order in orders:
        submit_upi_claim(order.id, fresh_reference())
    payments = list(Payment.objects.all())

    results = _run_together(10, lambda i: confirm_upi_payment(payments[i].id, actor=owner))

    assert not [r for r in results if isinstance(r, Exception)], results
    numbers = sorted(LuckyDecision.objects.values_list("participant_number", flat=True))
    assert numbers == list(range(1, 11))
    assert DailyCampaign.objects.get().paid_count == 10


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_one_payment_confirmed_twice_at_once_counts_once(
    salon, campaign, qr_on_file, owner, haircut
):
    order = place_order(salon, [haircut])
    submit_upi_claim(order.id, fresh_reference())
    payment = Payment.objects.get()

    results = _run_together(5, lambda i: confirm_upi_payment(payment.id, actor=owner))

    assert sum(1 for r in results if isinstance(r, Payment)) == 1
    assert sum(1 for r in results if isinstance(r, PaymentAlreadyDecided)) == 4
    assert DailyCampaign.objects.get().paid_count == 1
    assert LuckyDecision.objects.count() == 1


# --- regressions found by the bug hunt ----------------------------------------------


def test_a_decision_about_a_reference_the_customer_since_changed_is_refused(
    client, salon, campaign, qr_on_file, owner_auth, haircut
):
    """One UPI transfer must not back two orders. The owner checked reference X;
    the customer then swapped it for Y (freeing X for another order). Confirming
    must fail rather than approve Y on the strength of X."""
    order, payment = claimed(client, salon, [haircut], "9000000001")
    checked = payment.reference
    assert claim(client, order, "999988887777").status_code == 200  # swapped

    r = confirm(client, owner_auth, payment, reference=checked)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "payment_changed"
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.AWAITING_CONFIRMATION

    # With the current reference the decision goes through.
    assert confirm(client, owner_auth, payment).status_code == 200


def test_a_decision_must_name_the_reference(
    client, salon, campaign, qr_on_file, owner_auth, haircut
):
    _, payment = claimed(client, salon, [haircut], "9000000001")
    r = post(client, f"/api/v1/owner/payments/{payment.id}/confirm", owner_auth, {})
    assert r.status_code == 400


def test_a_repeat_entry_is_re_checked_when_the_first_claim_was_rejected(
    client, salon, campaign, qr_on_file, owner_auth, haircut
):
    """Same phone, two orders: B is skipped because A holds the day's entry. The
    owner rejects A (no money). Confirming B's real payment must now enter B."""
    set_winning_positions(campaign, [40])
    _, payment_a = claimed(client, salon, [haircut], "9000000001")
    order_b, payment_b = claimed(client, salon, [haircut], "9000000001")
    order_b.refresh_from_db()
    assert order_b.lucky_skip_reason == LuckySkipReason.REPEAT_ENTRY

    post(
        client,
        f"/api/v1/owner/payments/{payment_a.id}/reject",
        owner_auth,
        {"reference": payment_a.reference},
    )
    r = confirm(client, owner_auth, payment_b)
    assert r.status_code == 200
    assert r.json()["draw"]["status"] == "not_won"
    assert r.json()["draw"]["participant_number"] == 1


def test_a_repeat_entry_stays_skipped_while_the_first_claim_still_holds(
    client, salon, campaign, qr_on_file, owner_auth, haircut
):
    claimed(client, salon, [haircut], "9000000001")
    _, payment_b = claimed(client, salon, [haircut], "9000000001")
    r = confirm(client, owner_auth, payment_b)
    assert r.json()["draw"]["reason"] == LuckySkipReason.REPEAT_ENTRY


def test_public_slots_left_counts_places_held_by_unconfirmed_claims(
    client, salon, campaign, qr_on_file, haircut
):
    """The homepage must not show a free slot that an unconfirmed claim holds:
    a customer would pay into a draw that then refuses them."""
    DailyCampaign.objects.filter(pk=campaign.pk).update(capacity=2, lucky_count=1)
    claimed(client, salon, [haircut], "9000000001")
    claimed(client, salon, [haircut], "9000000002")

    today = client.get("/api/v1/promotion/today").json()
    assert today["paid_count"] == 0
    assert today["slots_remaining"] == 0
    assert today["is_open"] is False
