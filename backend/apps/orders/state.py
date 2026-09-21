"""Order state machine.

The transition table is the whole point: an order's status is the spine of the
money flow, and a status set by direct assignment somewhere in a view is how a
system ends up with a PAID order that never had a payment. Every change goes
through `transition`, and anything not in ALLOWED raises.
"""

from __future__ import annotations

from django.db import models

from common.exceptions import ConflictError


class OrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PAYMENT_PENDING = "PAYMENT_PENDING", "Payment pending"
    PAYMENT_FAILED = "PAYMENT_FAILED", "Payment failed"
    PAID = "PAID", "Paid"
    LUCKY_DECIDED = "LUCKY_DECIDED", "Lucky result decided"
    REFUND_PENDING = "REFUND_PENDING", "Refund pending"
    REFUNDED = "REFUNDED", "Refunded"
    REFUND_FAILED = "REFUND_FAILED", "Refund failed"
    COUPON_ACTIVE = "COUPON_ACTIVE", "Coupon active"
    REDEEMED = "REDEEMED", "Redeemed"
    CANCELLED = "CANCELLED", "Cancelled"


#: Legal transitions. Phase 3 only ever reaches DRAFT; later phases drive the
#: rest, but the table is declared in full now so no phase can invent an edge.
ALLOWED: dict[str, frozenset[str]] = {
    OrderStatus.DRAFT: frozenset({OrderStatus.PAYMENT_PENDING, OrderStatus.CANCELLED}),
    OrderStatus.PAYMENT_PENDING: frozenset(
        {OrderStatus.PAID, OrderStatus.PAYMENT_FAILED, OrderStatus.CANCELLED}
    ),
    # A failed payment is retryable: the customer may pay the same order again.
    OrderStatus.PAYMENT_FAILED: frozenset({OrderStatus.PAYMENT_PENDING, OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset({OrderStatus.LUCKY_DECIDED}),
    OrderStatus.LUCKY_DECIDED: frozenset({OrderStatus.COUPON_ACTIVE, OrderStatus.REFUND_PENDING}),
    OrderStatus.REFUND_PENDING: frozenset({OrderStatus.REFUNDED, OrderStatus.REFUND_FAILED}),
    # A failed refund is retried by the background worker, so it must be able to
    # go back to pending rather than becoming a dead end.
    OrderStatus.REFUND_FAILED: frozenset({OrderStatus.REFUND_PENDING}),
    OrderStatus.REFUNDED: frozenset({OrderStatus.COUPON_ACTIVE}),
    OrderStatus.COUPON_ACTIVE: frozenset({OrderStatus.REDEEMED}),
    # Terminal.
    OrderStatus.REDEEMED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


class InvalidOrderTransition(ConflictError):
    code = "invalid_order_transition"


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED.get(current, frozenset())


def check_transition(current: str, target: str) -> None:
    """Raise unless `current -> target` is a declared transition.

    A no-op transition (current == target) is rejected too. Silently accepting
    it would hide a double-processed payment, which is exactly the bug the
    idempotency work elsewhere exists to catch.
    """
    if not can_transition(current, target):
        raise InvalidOrderTransition(
            f"An order cannot move from {current} to {target}.",
            current_status=current,
            target_status=target,
        )
