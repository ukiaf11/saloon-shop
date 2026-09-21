"""UPI QR payments: the fallback while no payment gateway is configured.

The flow, and where trust enters it:

1. The customer places an order and sees the salon's QR (and, if the owner
   gave a UPI ID, a link that opens their UPI app with the amount filled in).
2. They pay in their own app, then give us the 12-digit UPI reference (UTR).
   That is a *claim*, not a payment: the order moves to PAYMENT_PENDING and a
   place in today's draw is held, but nothing is decided.
3. The owner finds the payment in their account and confirms it. Only then is
   the order PAID and given its draw number (apps.promotions.services
   .decide_lucky), in one transaction. Or they reject it, which frees the
   reference, the hold and the order for another attempt.

Row locks are always taken order first, then payment, on every path. A
customer correcting their reference while the owner confirms would otherwise
be able to deadlock the two.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.services import confirm_password
from apps.audit.services import record
from apps.customers.services import CustomerBlocked
from apps.orders.models import Order
from apps.orders.state import OrderStatus
from apps.payments.models import (
    LIVE_PAYMENT_STATUSES,
    Payment,
    PaymentProvider,
    PaymentSettings,
    PaymentStatus,
)
from apps.promotions.models import ReservationStatus, SlotReservation
from apps.promotions.services import decide_lucky, hold_draw_entry
from apps.refunds.services import create_lucky_refund
from common.exceptions import ConflictError, NotFound, ValidationFailed
from common.images import validate_image_file
from common.locks import lock_row, lock_row_or_none

logger = logging.getLogger(__name__)


class PaymentMethod:
    UPI_QR = "upi_qr"
    GATEWAY = "gateway"
    UNAVAILABLE = "unavailable"


UPI_REFERENCE = re.compile(r"^\d{12}$")
# name@bank -- the handle part is letters, digits, dot, dash, underscore; the
# provider part is letters and digits (okaxis, ybl, paytm, ...).
UPI_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,99}@[A-Za-z][A-Za-z0-9]{1,63}$")
QR_MAX_SIDE = 1200
# Below the general 5 MB image limit on purpose: Vercel refuses request bodies
# over 4.5 MB before they reach Django, so a larger upload would fail with a
# bare 413 instead of this message.
QR_MAX_BYTES = 4 * 1024 * 1024


class UpiPaymentsUnavailable(ConflictError):
    code = "upi_unavailable"
    message = "Paying by UPI QR is not available right now."


class DuplicateReference(ConflictError):
    code = "duplicate_reference"
    message = (
        "This UPI reference number has already been used for another booking. "
        "Please check the number in your payment app."
    )


class OrderNotPayable(ConflictError):
    code = "order_not_payable"
    message = "This order cannot take a payment right now."


class PaymentAlreadyDecided(ConflictError):
    code = "payment_already_decided"
    message = "This payment has already been confirmed or rejected."


# --- which method is live ----------------------------------------------------


def gateway_configured(salon) -> bool:
    """True once the owner's payment gateway credentials are saved and working.

    No gateway integration exists yet (Phase 5), so this is always False. When
    Phase 5 lands, this is the one place that learns about it: the QR fallback
    then switches itself off without anyone deleting the QR.
    """
    return False


def get_settings(salon, *, with_image: bool = False) -> PaymentSettings | None:
    qs = PaymentSettings.objects.filter(salon=salon)
    if not with_image:
        qs = qs.defer("qr_image")
    return qs.first()


def payment_method(salon, settings_row: PaymentSettings | None = None) -> str:
    if gateway_configured(salon):
        return PaymentMethod.GATEWAY
    row = settings_row if settings_row is not None else get_settings(salon)
    if row is not None and row.has_qr:
        return PaymentMethod.UPI_QR
    return PaymentMethod.UNAVAILABLE


# --- owner: the QR and UPI details --------------------------------------------


def normalise_qr_image(upload) -> tuple[bytes, int, int]:
    """Validate an uploaded QR and re-encode it as a clean PNG.

    Re-encoding is the security step, not a nicety: what gets served back to
    every customer is pixels this code produced, never bytes someone uploaded,
    so metadata (including GPS from a phone photo) and anything smuggled after
    the image data are gone. PNG because JPEG smears the edges of QR modules.
    """
    from PIL import Image, ImageOps

    if (getattr(upload, "size", 0) or 0) > QR_MAX_BYTES:
        raise DjangoValidationError(
            "The QR image must be 4 MB or smaller. A screenshot works best."
        )
    validate_image_file(upload)
    upload.seek(0)
    with Image.open(upload) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode in ("RGBA", "LA", "P", "PA"):
            # Flatten onto white. A plain convert("RGB") turns transparent
            # pixels black, and a QR on a black background does not scan.
            rgba = image.convert("RGBA")
            flat = Image.new("RGB", rgba.size, (255, 255, 255))
            flat.paste(rgba, mask=rgba.getchannel("A"))
            image = flat
        else:
            image = image.convert("RGB")
        if max(image.size) > QR_MAX_SIDE:
            image.thumbnail((QR_MAX_SIDE, QR_MAX_SIDE), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue(), image.width, image.height


def _settings_snapshot(row: PaymentSettings) -> dict:
    return {"qr_sha256": row.qr_sha256, "upi_id": row.upi_id, "payee_name": row.payee_name}


def update_payment_settings(
    salon,
    *,
    actor,
    password: str,
    qr_file=None,
    remove_qr: bool = False,
    upi_id: str | None = None,
    payee_name: str | None = None,
    request=None,
) -> PaymentSettings:
    """Change where customers' money goes. OWNER only, and re-authenticated.

    The password is asked again because this is the single most valuable thing
    a stolen session could do: swap the QR for someone else's and collect every
    payment until it is noticed.
    """
    confirm_password(actor, password)

    image = None
    if qr_file is not None:
        try:
            image = normalise_qr_image(qr_file)
        except DjangoValidationError:
            raise
        except Exception as exc:
            # A file can pass the header check and still fail to decode (a
            # truncated upload, for one). That is bad input, not a server fault.
            raise ValidationFailed("That file is not a readable image.") from exc

    if upi_id is not None:
        upi_id = upi_id.strip()
        if upi_id and not UPI_ID.match(upi_id):
            raise ValidationFailed("Enter a UPI ID like yourname@okaxis, or leave it empty.")
    if payee_name is not None:
        payee_name = " ".join(payee_name.split())[:100]

    with transaction.atomic():
        row, _ = PaymentSettings.objects.select_for_update().get_or_create(salon=salon)
        before = _settings_snapshot(row)

        if remove_qr:
            row.qr_image = None
            row.qr_content_type = ""
            row.qr_sha256 = ""
            row.qr_width = None
            row.qr_height = None
            row.qr_updated_at = timezone.now()
        if image is not None:
            data, width, height = image
            row.qr_image = data
            row.qr_content_type = "image/png"
            row.qr_sha256 = hashlib.sha256(data).hexdigest()
            row.qr_width = width
            row.qr_height = height
            row.qr_updated_at = timezone.now()
        if upi_id is not None:
            row.upi_id = upi_id
        if payee_name is not None:
            row.payee_name = payee_name
        row.updated_by = actor
        row.save()

        after = _settings_snapshot(row)
        if after != before:
            record(
                "payment_settings.updated",
                actor=actor,
                entity=row,
                before=before,
                after=after,
                request=request,
            )
    return row


# --- customer: claiming a payment ----------------------------------------------


def normalise_reference(raw: str) -> str:
    reference = re.sub(r"[\s-]", "", raw or "")
    if not UPI_REFERENCE.match(reference):
        raise ValidationFailed(
            "Enter the 12-digit UPI reference number (UTR) shown in your payment app."
        )
    return reference


def _ensure_reference_free(reference: str, *, exclude_pk=None) -> None:
    taken = Payment.objects.filter(
        provider=PaymentProvider.MANUAL_UPI,
        reference=reference,
        status__in=LIVE_PAYMENT_STATUSES,
    )
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    if taken.exists():
        raise DuplicateReference()


def submit_upi_claim(order_id, raw_reference: str) -> Order:
    """The customer says they have paid. Records the claim and holds a draw place.

    Idempotent for the same reference, and a customer who typed the reference
    wrong can correct it until the owner has decided.
    """
    reference = normalise_reference(raw_reference)

    with transaction.atomic():
        order = lock_row_or_none(Order.objects.select_related("salon", "customer"), pk=order_id)
        if order is None:
            raise NotFound("Order not found.")
        if payment_method(order.salon) != PaymentMethod.UPI_QR:
            raise UpiPaymentsUnavailable()
        if order.customer.is_blocked:
            raise CustomerBlocked()

        live = lock_row_or_none(
            Payment.objects,
            order=order,
            status=PaymentStatus.AWAITING_CONFIRMATION,
        )
        if live is not None:
            if live.reference != reference:
                _ensure_reference_free(reference, exclude_pk=live.pk)
                live.reference = reference
                try:
                    with transaction.atomic():
                        live.save(update_fields=["reference", "updated_at"])
                except IntegrityError as exc:
                    raise DuplicateReference() from exc
                logger.info("upi_claim_corrected", extra={"order_id": str(order.id)})
            return order

        if order.status not in (OrderStatus.DRAFT, OrderStatus.PAYMENT_FAILED):
            if order.paid_at is not None:
                raise OrderNotPayable("This order has already been paid.")
            raise OrderNotPayable()

        _ensure_reference_free(reference)
        order.transition_to(OrderStatus.PAYMENT_PENDING)
        try:
            with transaction.atomic():
                Payment.objects.create(
                    salon=order.salon,
                    order=order,
                    provider=PaymentProvider.MANUAL_UPI,
                    amount_paise=order.total_paise,
                    reference=reference,
                    submitted_at=timezone.now(),
                )
        except IntegrityError as exc:
            # Lost a race with another claim on the same reference.
            raise DuplicateReference() from exc

        hold_draw_entry(order, ttl_seconds=settings.UPI_CLAIM_HOLD_SECONDS)
        logger.info(
            "upi_claim_submitted",
            extra={"order_id": str(order.id), "amount_paise": order.total_paise},
        )
    return order


# --- owner: deciding a claim -------------------------------------------------------


def _lock_order_then_payment(payment_id) -> tuple[Order, Payment]:
    order_id = Payment.objects.filter(pk=payment_id).values_list("order_id", flat=True).first()
    if order_id is None:
        raise NotFound("Payment not found.")
    order = lock_row(Order.objects.select_related("salon", "customer"), pk=order_id)
    payment = lock_row(Payment.objects, pk=payment_id)
    if payment.status != PaymentStatus.AWAITING_CONFIRMATION:
        raise PaymentAlreadyDecided()
    return order, payment


def confirm_upi_payment(payment_id, *, actor, request=None) -> Payment:
    """The owner found the money. Mark the order paid and decide its draw entry.

    One transaction, per Doc 2 section 16: the payment, the order, the draw
    number, the winner count and any refund owed all commit together or not
    at all.
    """
    with transaction.atomic():
        order, payment = _lock_order_then_payment(payment_id)
        now = timezone.now()

        payment.status = PaymentStatus.CONFIRMED
        payment.decided_at = now
        payment.decided_by = actor
        payment.save(update_fields=["status", "decided_at", "decided_by", "updated_at"])

        order.transition_to(OrderStatus.PAID, save=False)
        order.paid_at = now
        order.save(update_fields=["status", "paid_at", "updated_at"])

        decision = decide_lucky(order, now=now)
        refund = None
        if decision is not None and decision.is_winner and decision.reward_refund_paise > 0:
            refund = create_lucky_refund(order, decision, payment)

        record(
            "payment.confirmed",
            actor=actor,
            entity=payment,
            after={
                "order": order.public_order_number,
                "amount_paise": payment.amount_paise,
                "reference": payment.reference,
                "participant_number": decision.participant_number if decision else None,
                "is_winner": decision.is_winner if decision else None,
                "skip_reason": order.lucky_skip_reason or None,
                "refund_paise": refund.amount_paise if refund else 0,
            },
            request=request,
        )
    return payment


def reject_upi_payment(payment_id, *, actor, reason: str = "", request=None) -> Payment:
    """The money is not there. The order can be paid again with a new claim."""
    reason = " ".join((reason or "").split())[:200]
    with transaction.atomic():
        order, payment = _lock_order_then_payment(payment_id)

        payment.status = PaymentStatus.REJECTED
        payment.decided_at = timezone.now()
        payment.decided_by = actor
        payment.rejection_reason = reason
        payment.save(
            update_fields=[
                "status",
                "decided_at",
                "decided_by",
                "rejection_reason",
                "updated_at",
            ]
        )
        order.transition_to(OrderStatus.PAYMENT_FAILED)
        # Give the held draw place back to the day.
        SlotReservation.objects.filter(order=order, status=ReservationStatus.ACTIVE).update(
            status=ReservationStatus.CANCELLED, updated_at=timezone.now()
        )
        record(
            "payment.rejected",
            actor=actor,
            entity=payment,
            after={
                "order": order.public_order_number,
                "reference": payment.reference,
                "reason": reason,
            },
            request=request,
        )
    return payment
