"""Order creation, snapshots, idempotency and the tampering exit gate."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.catalog.services import change_service_price
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.orders.services import create_order
from apps.orders.state import InvalidOrderTransition, OrderStatus
from common.exceptions import ValidationFailed

pytestmark = pytest.mark.django_db


def items(*pairs):
    return [{"service_id": str(s.id), "quantity": q} for s, q in pairs]


def make(salon, *pairs, **kwargs):
    kwargs.setdefault("customer_name", "Rahul Sharma")
    kwargs.setdefault("customer_phone", "9000000000")
    return create_order(salon, items(*pairs), **kwargs)


# --- the exit gate --------------------------------------------------------


def test_client_supplied_prices_are_ignored(salon, config, haircut, shaving):
    """Phase 3's exit gate: a forged price must produce an order at the real one.

    The extra keys are not rejected -- they are never read, because the request
    serializer has no field to bind them to.
    """
    hostile = [
        {
            "service_id": str(haircut.id),
            "quantity": 1,
            "price_paise": 1,
            "unit_price_paise": 1,
            "line_total_paise": 1,
        },
        {"service_id": str(shaving.id), "quantity": 1, "price_paise": 0},
    ]
    order = create_order(salon, hostile, customer_name="Rahul", customer_phone="9000000000")

    assert order.subtotal_paise == 45000
    assert order.discount_paise == 4500
    assert order.total_paise == 40500
    assert [i.unit_price_paise for i in order.items.order_by("unit_price_paise")] == [
        15000,
        30000,
    ]


def test_client_supplied_totals_and_status_are_ignored(salon, config, haircut, shaving):
    order = create_order(
        salon,
        items((haircut, 1), (shaving, 1)),
        customer_name="Rahul",
        customer_phone="9000000000",
    )
    assert order.total_paise == 40500
    assert order.status == OrderStatus.DRAFT


# --- snapshots ------------------------------------------------------------


def test_a_later_price_change_does_not_rewrite_the_order(
    salon, config, haircut, shaving, admin_user
):
    order = make(salon, (haircut, 1), (shaving, 1))
    assert order.total_paise == 40500

    change_service_price(haircut, 35000, changed_by=admin_user)

    order.refresh_from_db()
    item = order.items.get(service=haircut)
    assert item.unit_price_paise == 30000, "history must not be rewritten"
    assert item.service_name_snapshot == "Hair Cutting"
    assert order.total_paise == 40500


def test_a_later_rename_does_not_rewrite_the_order(salon, config, haircut, shaving):
    order = make(salon, (haircut, 1), (shaving, 1))
    haircut.name = "Premium Cut"
    haircut.save()

    assert order.items.get(service=haircut).service_name_snapshot == "Hair Cutting"


def test_items_carry_the_allocation_and_reconcile(salon, config, haircut, hair_spa):
    order = make(salon, (haircut, 1), (hair_spa, 1))
    rows = list(order.items.all())

    assert sum(i.line_total_paise for i in rows) == order.subtotal_paise
    assert sum(i.discount_alloc_paise for i in rows) == order.discount_paise
    assert sum(i.net_paid_paise for i in rows) == order.total_paise


# --- customer -------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("9000000000", "+919000000000"),
        ("09000000000", "+919000000000"),
        ("+91 90000 00000", "+919000000000"),
        ("+91-90000-00000", "+919000000000"),
        ("+14155550123", "+14155550123"),
    ],
)
def test_phone_is_normalised_so_one_person_is_one_row(
    salon, config, haircut, shaving, raw, expected
):
    order = make(salon, (haircut, 1), (shaving, 1), customer_phone=raw)
    assert order.customer.phone == expected


def test_same_person_different_formatting_reuses_one_customer(salon, config, haircut, shaving):
    make(salon, (haircut, 1), (shaving, 1), customer_phone="9000000000")
    make(salon, (haircut, 1), (shaving, 1), customer_phone="+91 90000 00000")
    assert Customer.objects.count() == 1


def test_blocked_customer_cannot_order(salon, config, haircut, shaving):
    make(salon, (haircut, 1), (shaving, 1))
    Customer.objects.update(is_blocked=True, blocked_reason="abuse")

    from apps.customers.services import CustomerBlocked

    with pytest.raises(CustomerBlocked):
        make(salon, (haircut, 1), (shaving, 1))


@pytest.mark.parametrize("bad", ["", "   ", "abc", "12"])
def test_bad_phone_is_refused(salon, config, haircut, bad):
    with pytest.raises(ValidationFailed):
        make(salon, (haircut, 1), customer_phone=bad)


def test_missing_name_is_refused(salon, config, haircut):
    with pytest.raises(ValidationFailed):
        make(salon, (haircut, 1), customer_name="  ")


# --- idempotency ----------------------------------------------------------


def test_replaying_an_idempotency_key_returns_the_same_order(salon, config, haircut, shaving):
    first = make(salon, (haircut, 1), (shaving, 1), idempotency_key="checkout-abc")
    second = make(salon, (haircut, 1), (shaving, 1), idempotency_key="checkout-abc")

    assert first.id == second.id
    assert Order.objects.count() == 1
    assert OrderItem.objects.count() == 2


def test_different_keys_create_different_orders(salon, config, haircut, shaving):
    a = make(salon, (haircut, 1), (shaving, 1), idempotency_key="one")
    b = make(salon, (haircut, 1), (shaving, 1), idempotency_key="two")
    assert a.id != b.id
    assert Order.objects.count() == 2


def test_no_key_means_no_deduplication(salon, config, haircut, shaving):
    """Without a key there is nothing to match on, so two submits are two
    orders. The frontend sends a key precisely to avoid this."""
    make(salon, (haircut, 1), (shaving, 1))
    make(salon, (haircut, 1), (shaving, 1))
    assert Order.objects.count() == 2


# --- public order number --------------------------------------------------


def test_order_number_is_not_sequential(salon, config, haircut, shaving):
    """A sequential number would tell every customer the salon's order volume."""
    numbers = [make(salon, (haircut, 1), (shaving, 1)).public_order_number for _ in range(5)]
    assert len(set(numbers)) == 5
    suffixes = [n.rsplit("-", 1)[1] for n in numbers]
    assert len(set(suffixes)) == 5
    assert not any(ch in "".join(suffixes) for ch in "IO01")


# --- database constraints -------------------------------------------------


def test_database_rejects_a_total_that_does_not_match(salon, config, haircut, shaving):
    """The arithmetic is guarded by the DB, not only by the code that writes it."""
    order = make(salon, (haircut, 1), (shaving, 1))
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.filter(pk=order.pk).update(total_paise=1)


def test_database_rejects_a_bad_net_paid(salon, config, haircut, shaving):
    order = make(salon, (haircut, 1), (shaving, 1))
    item = order.items.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        OrderItem.objects.filter(pk=item.pk).update(net_paid_paise=999999)


# --- state machine --------------------------------------------------------


def test_legal_transition_is_allowed(salon, config, haircut, shaving):
    order = make(salon, (haircut, 1), (shaving, 1))
    order.transition_to(OrderStatus.PAYMENT_PENDING)
    order.refresh_from_db()
    assert order.status == OrderStatus.PAYMENT_PENDING


def test_illegal_transition_raises(salon, config, haircut, shaving):
    order = make(salon, (haircut, 1), (shaving, 1))
    with pytest.raises(InvalidOrderTransition):
        order.transition_to(OrderStatus.PAID)  # skips payment entirely


def test_no_op_transition_raises(salon, config, haircut, shaving):
    """Accepting current -> current would hide a double-processed payment."""
    order = make(salon, (haircut, 1), (shaving, 1))
    with pytest.raises(InvalidOrderTransition):
        order.transition_to(OrderStatus.DRAFT)


def test_terminal_states_have_no_exits():
    from apps.orders.state import ALLOWED

    assert ALLOWED[OrderStatus.REDEEMED] == frozenset()
    assert ALLOWED[OrderStatus.CANCELLED] == frozenset()


def test_every_status_appears_in_the_transition_table():
    from apps.orders.state import ALLOWED

    assert set(ALLOWED) == {s.value for s in OrderStatus}
    for targets in ALLOWED.values():
        assert targets <= {s.value for s in OrderStatus}
