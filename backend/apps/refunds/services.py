from __future__ import annotations

import logging
import re

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from apps.orders.models import Order
from apps.orders.state import OrderStatus
from apps.refunds.models import Refund, RefundMethod, RefundReason, RefundStatus
from common.exceptions import ConflictError, NotFound, ValidationFailed
from common.locks import lock_row, lock_row_or_none

logger = logging.getLogger(__name__)

_UPI_REFERENCE = re.compile(r"^\d{12}$")


class RefundAlreadySent(ConflictError):
    code = "refund_already_sent"
    message = "This refund is already marked as sent."


def create_lucky_refund(order: Order, decision, payment) -> Refund:
    """Record what a winner is owed and move the order to REFUND_PENDING.

    Runs inside the confirmation transaction, right after the decision.
    """
    refund = Refund.objects.create(
        salon=order.salon,
        order=order,
        payment=payment,
        reason=RefundReason.LUCKY_REWARD,
        amount_paise=decision.reward_refund_paise,
    )
    order.transition_to(OrderStatus.REFUND_PENDING)
    logger.info(
        "refund_created",
        extra={
            "refund_id": str(refund.id),
            "order_id": str(order.id),
            "amount_paise": refund.amount_paise,
        },
    )
    return refund


def mark_refund_sent(refund_id, *, method: str, reference: str, actor, request=None) -> Refund:
    """The owner has sent the money. OWNER only (REQUIREMENTS.md section 5)."""
    reference = re.sub(r"[\s-]", "", reference or "")
    if method not in RefundMethod.values:
        raise ValidationFailed("Choose how the refund was sent.")
    if method == RefundMethod.UPI and not _UPI_REFERENCE.match(reference):
        raise ValidationFailed("Enter the 12-digit UPI reference of the refund you sent.")
    if method == RefundMethod.CASH:
        reference = ""

    order_id = Refund.objects.filter(pk=refund_id).values_list("order_id", flat=True).first()
    if order_id is None:
        raise NotFound("Refund not found.")

    with transaction.atomic():
        # Order first, then refund: the same order every money path takes locks
        # in, so two of them can never deadlock on each other.
        order = lock_row(Order.objects, pk=order_id)
        refund = lock_row_or_none(Refund.objects, pk=refund_id)
        if refund.status == RefundStatus.SENT:
            raise RefundAlreadySent()

        refund.status = RefundStatus.SENT
        refund.method = method
        refund.reference = reference
        refund.sent_at = timezone.now()
        refund.sent_by = actor
        refund.save(
            update_fields=["status", "method", "reference", "sent_at", "sent_by", "updated_at"]
        )
        order.transition_to(OrderStatus.REFUNDED)
        record(
            "refund.sent",
            actor=actor,
            entity=refund,
            after={
                "order": order.public_order_number,
                "amount_paise": refund.amount_paise,
                "method": method,
                "reference": reference,
            },
            request=request,
        )
    return refund
