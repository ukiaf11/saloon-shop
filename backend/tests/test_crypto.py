"""Field encryption guards.

The campaign seed decides who gets money back. Storing it under a key derived
from a leaked SECRET_KEY would protect nothing, so production must refuse to
run without a real one.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from common.crypto import DecryptionFailed, decrypt, encrypt, generate_key


def test_round_trips():
    assert decrypt(encrypt("lucky seed")) == b"lucky seed"


def test_bytes_round_trip():
    assert decrypt(encrypt(b"\x00\x01\xff")) == b"\x00\x01\xff"


def test_ciphertext_does_not_contain_the_plaintext():
    assert "lucky seed" not in encrypt("lucky seed")


def test_same_plaintext_encrypts_differently_each_time():
    """Fernet includes a random IV, so identical seeds are not linkable by
    comparing stored ciphertext."""
    assert encrypt("same") != encrypt("same")


@override_settings(FIELD_ENCRYPTION_KEY="", DEBUG=False)
def test_production_refuses_to_encrypt_without_a_key():
    with pytest.raises(ImproperlyConfigured):
        encrypt("x")


@override_settings(FIELD_ENCRYPTION_KEY="", DEBUG=True)
def test_debug_derives_a_key_for_convenience():
    assert decrypt(encrypt("x")) == b"x"


@override_settings(FIELD_ENCRYPTION_KEY="clearly-not-a-fernet-key")
def test_a_malformed_key_is_rejected_loudly():
    with pytest.raises(ImproperlyConfigured):
        encrypt("x")


def test_wrong_key_fails_loudly_rather_than_returning_junk():
    """A rotated key makes that day's result unverifiable, so it must raise."""
    token = encrypt("secret")
    with override_settings(FIELD_ENCRYPTION_KEY=generate_key()):
        with pytest.raises(DecryptionFailed):
            decrypt(token)
