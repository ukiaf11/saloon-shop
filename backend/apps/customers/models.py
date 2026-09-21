from __future__ import annotations

from django.db import models

from common.models import UUIDTimestampedModel


class Customer(UUIDTimestampedModel):
    """A person who has ordered. Customers never log in -- there is no password
    and no session. The phone number is the identity, which is why it is unique
    and why entry limits are keyed on it (Doc 2 section 28)."""

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)

    phone_verified_at = models.DateTimeField(null=True, blank=True)

    # Set by an owner after abuse, not by automation. Blocking someone must be
    # a deliberate, attributable act.
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True)

    class Meta:
        db_table = "customer"
        indexes = [models.Index(fields=["phone"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.masked_phone})"

    @property
    def masked_phone(self) -> str:
        from common.masking import mask_phone

        return mask_phone(self.phone)

    @property
    def is_phone_verified(self) -> bool:
        return self.phone_verified_at is not None
