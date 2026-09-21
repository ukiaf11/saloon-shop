"""The lucky engine.

Winning positions for a day are drawn **before** anyone participates, from a
256-bit secret seed. A customer who pays is given the next participant number;
they win if that number is one of the drawn positions. Nobody -- including the
salon -- can move the positions once the day has started, and the commitment
hash published at creation lets that be proved afterwards.

Why not draw per payment
------------------------
Calling random() at each payment cannot guarantee exactly W winners, cannot be
audited after the fact, and lets anyone who can re-run the code change an
outcome. Doc 2 section 15 rules it out explicitly.

Why HMAC rather than random.sample
----------------------------------
The selection must be reproducible years later and verifiable by an auditor
using any language. `random.sample` is seeded-deterministic but its algorithm is
a CPython implementation detail: a future Python could change it and silently
make every past campaign unverifiable. Sorting positions by HMAC-SHA256(seed, i)
is specified by the standard, stable forever, and reimplementable in ten lines
of any language.

Uniformity: HMAC outputs are indistinguishable from random, so ordering by them
is a uniformly random permutation; taking the first W is a uniform sample
without replacement.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
import uuid

__all__ = [
    "SEED_BYTES",
    "commitment_for",
    "generate_seed",
    "verify_commitment",
    "winning_positions",
]

SEED_BYTES = 32  # 256 bits


def generate_seed() -> bytes:
    """A cryptographically secure seed. The only source of unpredictability."""
    return secrets.token_bytes(SEED_BYTES)


def commitment_for(
    seed: bytes,
    *,
    salon_id: uuid.UUID | str,
    campaign_date: dt.date,
    capacity: int,
    lucky_count: int,
) -> str:
    """SHA256 over the seed and the parameters it was drawn for.

    Binding the parameters into the hash is what stops a later claim that the
    same seed was drawn for a different capacity -- which would imply a
    different set of winning positions. Doc 2 section 14.
    """
    payload = b"|".join(
        [
            seed,
            str(salon_id).encode(),
            campaign_date.isoformat().encode(),
            str(capacity).encode(),
            str(lucky_count).encode(),
        ]
    )
    return hashlib.sha256(payload).hexdigest()


def verify_commitment(
    seed: bytes,
    commitment: str,
    *,
    salon_id: uuid.UUID | str,
    campaign_date: dt.date,
    capacity: int,
    lucky_count: int,
) -> bool:
    """Check a revealed seed against its published commitment.

    Constant-time: this runs when an auditor or owner challenges a result, and
    leaking hash-comparison timing there would be careless.
    """
    expected = commitment_for(
        seed,
        salon_id=salon_id,
        campaign_date=campaign_date,
        capacity=capacity,
        lucky_count=lucky_count,
    )
    return hmac.compare_digest(expected, commitment)


def winning_positions(seed: bytes, capacity: int, lucky_count: int) -> list[int]:
    """Draw `lucky_count` distinct positions from 1..capacity.

    Deterministic in the seed, uniform, duplicate-free, and returned sorted
    ascending. Sorting the result leaks nothing: the set is what matters, and
    the draw order is not used anywhere.
    """
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    if lucky_count < 0:
        raise ValueError("lucky_count cannot be negative")
    if lucky_count > capacity:
        raise ValueError("lucky_count cannot exceed capacity")
    if lucky_count == 0:
        return []

    def rank(position: int) -> bytes:
        return hmac.new(seed, str(position).encode(), hashlib.sha256).digest()

    # Ties are impossible in practice (a SHA256 collision), but ordering by
    # (rank, position) keeps the result total and reproducible regardless.
    ordered = sorted(range(1, capacity + 1), key=lambda p: (rank(p), p))
    return sorted(ordered[:lucky_count])


def is_winning_position(position: int, positions: list[int]) -> bool:
    return position in positions
