"""Customer lookup and phone normalisation."""

from __future__ import annotations

import re

from django.db import transaction

from apps.customers.models import Customer
from common.exceptions import PermissionDenied, ValidationFailed

_DIGITS = re.compile(r"\D")

# The salon is in India and the public site collects Indian mobile numbers.
# A bare 10-digit entry is the common case and is assumed to be +91; anything
# already carrying a country code is respected as given.
DEFAULT_COUNTRY_CODE = "91"
INDIAN_MOBILE_LENGTH = 10


class CustomerBlocked(PermissionDenied):
    code = "customer_blocked"
    message = "This account cannot place an order. Please contact the salon."


def normalise_phone(raw: str) -> str:
    """Return an E.164 phone number, or raise ValidationFailed.

    Normalising at the boundary means one customer cannot become two rows by
    typing "9000000000" once and "+91 90000 00000" the next time.
    """
    if not raw or not raw.strip():
        raise ValidationFailed("A phone number is required.")

    had_plus = raw.strip().startswith("+")
    digits = _DIGITS.sub("", raw)

    if not digits:
        raise ValidationFailed("Enter a valid phone number.")

    if not had_plus:
        if len(digits) == INDIAN_MOBILE_LENGTH:
            digits = DEFAULT_COUNTRY_CODE + digits
        elif digits.startswith("0") and len(digits) == INDIAN_MOBILE_LENGTH + 1:
            # A leading trunk zero, as dialled domestically.
            digits = DEFAULT_COUNTRY_CODE + digits[1:]

    if not (10 <= len(digits) <= 15):  # E.164 allows at most 15 digits
        raise ValidationFailed("Enter a valid phone number.")

    return f"+{digits}"


@transaction.atomic
def get_or_create_customer(*, name: str, phone: str, email: str = "") -> Customer:
    """Find the customer by normalised phone, creating one if needed.

    The name and email are refreshed from the latest order, because a customer
    correcting their own details should not have to contact the salon. A
    blocked customer is refused before any order work happens.
    """
    normalised = normalise_phone(phone)
    name = (name or "").strip()
    if not name:
        raise ValidationFailed("A name is required.")

    customer, created = Customer.objects.select_for_update().get_or_create(
        phone=normalised,
        defaults={"name": name[:120], "email": (email or "").strip()},
    )

    if customer.is_blocked:
        raise CustomerBlocked()

    if not created:
        changed = False
        if name and customer.name != name[:120]:
            customer.name = name[:120]
            changed = True
        clean_email = (email or "").strip()
        if clean_email and customer.email != clean_email:
            customer.email = clean_email
            changed = True
        if changed:
            customer.save(update_fields=["name", "email", "updated_at"])

    return customer
