"""Redaction helpers.

REQUIREMENTS.md 3.6 forbids these values from reaching logs or audit records:
gateway secrets, CVV, card numbers, UPI PIN, OTP, raw webhook payloads. This
module is the single place that decides what a sensitive key looks like, so the
rule is enforced once rather than remembered at every call site.
"""

from __future__ import annotations

from typing import Any

REDACTED = "[REDACTED]"

SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "key_secret",
    "webhook_secret",
    "cvv",
    "card_number",
    "cardnumber",
    "pan",
    "pin",
    "otp",
    "signature",
    "seed",
    "winning_position",
    "private",
    "mfa",
)


#: Keys that match a sensitive substring but are safe, and useful, to log.
#: `seed_commitment` is a SHA256 hash published precisely so a result can be
#: verified later -- it reveals nothing about the seed. Keep this list tiny and
#: justify every entry; it is easier to add one key here than to weaken the
#: denylist and leak something else.
PUBLIC_KEY_EXCEPTIONS = frozenset({"seed_commitment"})


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in PUBLIC_KEY_EXCEPTIONS:
        return False
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def mask_value(value: str, keep: int = 4) -> str:
    """Mask all but the last ``keep`` characters -- used for key IDs."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


def mask_phone(phone: str) -> str:
    return mask_value(phone, keep=4)


def redact(data: Any, _depth: int = 0) -> Any:
    """Recursively redact sensitive keys in a dict/list structure."""
    if _depth > 12:
        return REDACTED
    if isinstance(data, dict):
        return {
            k: (REDACTED if is_sensitive_key(str(k)) else redact(v, _depth + 1))
            for k, v in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [redact(v, _depth + 1) for v in data]
    return data
