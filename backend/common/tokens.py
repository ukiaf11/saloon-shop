"""Opaque token generation.

Coupon URLs must not be guessable and must not encode anything about the
customer (REQUIREMENTS.md 3.4 / Doc 2 sections 25-26).
"""

from __future__ import annotations

import secrets
import string

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1 -- read aloud safely


def opaque_token(n_bytes: int = 32) -> str:
    """URL-safe token. 32 bytes = 256 bits, far above the 128-bit floor."""
    return secrets.token_urlsafe(n_bytes)


def human_code(length: int = 8) -> str:
    """Short code a receptionist can type from a customer's phone screen."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def numeric_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))
