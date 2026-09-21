"""The lucky engine.

Doc 3 section 49 lists what must hold for every campaign. These are those
properties, checked across many (capacity, lucky_count) pairs rather than one.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from apps.promotions.lucky import (
    SEED_BYTES,
    commitment_for,
    generate_seed,
    verify_commitment,
    winning_positions,
)

SALON = uuid.UUID("11111111-1111-4111-8111-111111111111")
DATE = dt.date(2026, 9, 21)


def test_seed_is_256_bits():
    assert len(generate_seed()) == SEED_BYTES == 32


def test_two_seeds_differ():
    assert generate_seed() != generate_seed()


# --- position drawing -----------------------------------------------------


@given(
    capacity=st.integers(min_value=1, max_value=500),
    fraction=st.floats(min_value=0, max_value=1),
)
@settings(max_examples=250, deadline=None)
def test_exactly_w_unique_positions_in_range(capacity, fraction):
    lucky_count = min(int(capacity * fraction), capacity)
    positions = winning_positions(generate_seed(), capacity, lucky_count)

    assert len(positions) == lucky_count
    assert len(set(positions)) == lucky_count, "no duplicates"
    assert all(1 <= p <= capacity for p in positions)
    assert positions == sorted(positions)


def test_same_seed_and_config_reproduce_the_same_draw():
    """An auditor must be able to re-derive the result years later."""
    seed = generate_seed()
    first = winning_positions(seed, 40, 5)
    for _ in range(20):
        assert winning_positions(seed, 40, 5) == first


def test_different_seeds_usually_differ():
    draws = {tuple(winning_positions(generate_seed(), 40, 5)) for _ in range(200)}
    # Collisions among C(40,5) = 658,008 possibilities should be vanishingly rare.
    assert len(draws) > 190


def test_changing_capacity_changes_the_draw():
    seed = generate_seed()
    assert winning_positions(seed, 40, 5) != winning_positions(seed, 100, 5)


def test_zero_lucky_count_draws_nothing():
    assert winning_positions(generate_seed(), 40, 0) == []


def test_lucky_count_equal_to_capacity_draws_everything():
    assert winning_positions(generate_seed(), 10, 10) == list(range(1, 11))


@pytest.mark.parametrize("capacity,lucky", [(0, 0), (-1, 0), (10, 11), (10, -1)])
def test_invalid_parameters_raise(capacity, lucky):
    with pytest.raises(ValueError):
        winning_positions(generate_seed(), capacity, lucky)


def test_draw_is_uniform_across_positions():
    """No position may be systematically favoured -- that would be riggable."""
    import collections

    counts = collections.Counter()
    rounds = 3000
    for _ in range(rounds):
        counts.update(winning_positions(generate_seed(), 20, 4))

    expected = rounds * 4 / 20
    for position in range(1, 21):
        # Generous band: this catches a broken draw, not normal variance.
        assert 0.75 * expected < counts[position] < 1.25 * expected


# --- commitment -----------------------------------------------------------


def test_commitment_verifies_against_its_seed():
    seed = generate_seed()
    c = commitment_for(seed, salon_id=SALON, campaign_date=DATE, capacity=40, lucky_count=5)
    assert verify_commitment(
        seed, c, salon_id=SALON, campaign_date=DATE, capacity=40, lucky_count=5
    )


def test_commitment_rejects_a_different_seed():
    c = commitment_for(
        generate_seed(), salon_id=SALON, campaign_date=DATE, capacity=40, lucky_count=5
    )
    assert not verify_commitment(
        generate_seed(), c, salon_id=SALON, campaign_date=DATE, capacity=40, lucky_count=5
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("capacity", 41),
        ("lucky_count", 6),
        ("campaign_date", dt.date(2026, 9, 22)),
        ("salon_id", uuid.UUID("22222222-2222-4222-8222-222222222222")),
    ],
)
def test_commitment_binds_every_parameter(field, value):
    """Binding the parameters is what stops a later claim that the same seed was
    drawn for a different capacity -- which would mean different positions."""
    seed = generate_seed()
    base = {
        "salon_id": SALON,
        "campaign_date": DATE,
        "capacity": 40,
        "lucky_count": 5,
    }
    c = commitment_for(seed, **base)

    tampered = {**base, field: value}
    assert not verify_commitment(seed, c, **tampered)
