"""Field-level encryption for secrets that must survive in the database.

Used for the daily campaign seed and its winning positions. Those values decide
who wins money back, so they are encrypted at rest and never leave the server:
anyone who could read them could tell a friend which position to take.

The key comes from the environment (a secret manager in production). In DEBUG a
key is derived from SECRET_KEY so a developer can run the stack without extra
setup -- production refuses to boot without a real one, because a key derived
from a leaked SECRET_KEY protects nothing.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

__all__ = ["DecryptionFailed", "decrypt", "encrypt"]


class DecryptionFailed(Exception):
    """Raised when ciphertext cannot be read with the configured key.

    Almost always means the key was rotated without re-encrypting, which for a
    campaign seed makes that day's result unverifiable. It must surface loudly
    rather than be swallowed.
    """


def _fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""

    if not key:
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                "FIELD_ENCRYPTION_KEY must be set outside DEBUG. The campaign "
                "seed cannot be stored without it."
            )
        # Development convenience only. Deterministic so a restart can still
        # read what the previous run wrote.
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()

    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY is not a valid Fernet key. Generate one with "
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"`.'
        ) from exc


def encrypt(plaintext: str | bytes) -> str:
    """Encrypt to a storable ASCII token."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode()
    return _fernet().encrypt(plaintext).decode()


def decrypt(token: str) -> bytes:
    """Decrypt a token produced by `encrypt`."""
    try:
        return _fernet().decrypt(token.encode() if isinstance(token, str) else token)
    except InvalidToken as exc:
        raise DecryptionFailed(
            "Stored ciphertext could not be decrypted with the configured key."
        ) from exc


def generate_key() -> str:
    """A fresh Fernet key, for provisioning an environment."""
    return Fernet.generate_key().decode()
