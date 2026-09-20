"""Money and discount-allocation tests.

The allocator feeds partial winner refunds (REQUIREMENTS.md 8.1), so the two
sum invariants are checked property-based across randomly generated baskets as
required by 8.3 -- not just on a handful of hand-picked examples.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from common.money import (
    MoneyError,
    allocate_discount,
    format_inr,
    percent_of,
)

# --- worked example from REQUIREMENTS.md 8.1 -----------------------------


def test_locked_worked_example():
    """Haircut 300 + Hair Spa 800 with 10% off -> refundable 270, retained 720."""
    subtotal = 30000 + 80000
    discount = percent_of(subtotal, 10)
    assert discount == 11000

    alloc = allocate_discount([("haircut", 30000), ("spa", 80000)], discount)

    assert alloc.by_key("haircut").discount_alloc_paise == 3000
    assert alloc.by_key("haircut").net_paid_paise == 27000
    assert alloc.by_key("spa").discount_alloc_paise == 8000
    assert alloc.by_key("spa").net_paid_paise == 72000
    assert alloc.total_paise == 99000


def test_largest_remainder_distributes_leftover_paise():
    """3 lines of 1 paise sharing a 2 paise discount: 2 lines get 1, one gets 0."""
    alloc = allocate_discount([("a", 1), ("b", 1), ("c", 1)], 2)
    allocations = sorted(line.discount_alloc_paise for line in alloc.lines)
    assert allocations == [0, 1, 1]
    assert sum(allocations) == 2


def test_tie_break_is_deterministic_on_key():
    """Identical remainders must resolve the same way every run."""
    lines = [("c", 100), ("a", 100), ("b", 100)]
    first = allocate_discount(lines, 2)
    for _ in range(50):
        again = allocate_discount(lines, 2)
        assert [line.discount_alloc_paise for line in first.lines] == [
            line.discount_alloc_paise for line in again.lines
        ]
    # Ascending key wins the leftover paise: a and b, not c.
    assert first.by_key("a").discount_alloc_paise == 1
    assert first.by_key("b").discount_alloc_paise == 1
    assert first.by_key("c").discount_alloc_paise == 0


def test_zero_discount_allocates_nothing():
    alloc = allocate_discount([("a", 500), ("b", 700)], 0)
    assert all(line.discount_alloc_paise == 0 for line in alloc.lines)
    assert alloc.total_paise == 1200


def test_discount_may_equal_subtotal():
    alloc = allocate_discount([("a", 500), ("b", 500)], 1000)
    assert alloc.total_paise == 0
    assert all(line.net_paid_paise == 0 for line in alloc.lines)


def test_discount_above_subtotal_is_rejected():
    with pytest.raises(MoneyError):
        allocate_discount([("a", 500)], 501)


def test_negative_line_is_rejected():
    with pytest.raises(MoneyError):
        allocate_discount([("a", -1)], 0)


def test_percent_of_truncates_in_the_customer_safe_direction():
    # 999 paise at 10% is 99.9 -> 99, never 100. A discount must not exceed
    # the advertised percentage.
    assert percent_of(999, 10) == 99
    assert percent_of(0, 10) == 0
    assert percent_of(100, 0) == 0


def test_percent_of_rejects_out_of_range():
    with pytest.raises(MoneyError):
        percent_of(100, 101)
    with pytest.raises(MoneyError):
        percent_of(-1, 10)


def test_format_inr_uses_indian_grouping():
    assert format_inr(30000) == "₹300"
    assert format_inr(40500) == "₹405"
    assert format_inr(99) == "₹0.99"
    assert format_inr(1245000) == "₹12,450"
    assert format_inr(123456789) == "₹12,34,567.89"
    assert format_inr(1000000000) == "₹1,00,00,000"
    assert format_inr(-30000) == "-₹300"


# --- property-based invariants (REQUIREMENTS.md 8.3) ---------------------

basket = st.lists(
    st.tuples(
        st.integers(min_value=1, max_value=999),  # quantity-bearing line id
        st.integers(min_value=0, max_value=5_000_00),  # line total in paise
    ),
    min_size=1,
    max_size=25,
)


@given(lines=basket, percent=st.integers(min_value=0, max_value=100))
@settings(max_examples=500, deadline=None)
def test_allocation_invariants_hold_for_any_basket(lines, percent):
    keyed = [(f"item-{i}-{k}", total) for i, (k, total) in enumerate(lines)]
    subtotal = sum(total for _, total in keyed)
    discount = percent_of(subtotal, percent)

    alloc = allocate_discount(keyed, discount)

    # The two invariants the spec names explicitly.
    assert sum(line.discount_alloc_paise for line in alloc.lines) == discount
    assert sum(line.net_paid_paise for line in alloc.lines) == subtotal - discount

    # And the per-line sanity bound that makes a refund computable.
    for line in alloc.lines:
        assert 0 <= line.discount_alloc_paise <= line.line_total_paise
        assert line.net_paid_paise >= 0


@given(lines=basket, percent=st.integers(min_value=0, max_value=100))
@settings(max_examples=200, deadline=None)
def test_allocation_is_reproducible(lines, percent):
    """Same input must give the same allocation -- a stored order has to be
    recomputable during reconciliation."""
    keyed = [(f"item-{i}", total) for i, (_, total) in enumerate(lines)]
    discount = percent_of(sum(t for _, t in keyed), percent)
    first = allocate_discount(keyed, discount)
    second = allocate_discount(keyed, discount)
    assert [line.discount_alloc_paise for line in first.lines] == [
        line.discount_alloc_paise for line in second.lines
    ]


@given(
    lines=st.lists(
        st.tuples(st.integers(1, 999), st.integers(1, 100_00)),
        min_size=2,
        max_size=12,
    )
)
@settings(max_examples=200, deadline=None)
def test_proportionality_error_is_at_most_one_paise(lines):
    """Largest-remainder keeps every line within 1 paise of its exact share."""
    keyed = [(f"item-{i}", total) for i, (_, total) in enumerate(lines)]
    subtotal = sum(t for _, t in keyed)
    discount = percent_of(subtotal, 10)
    alloc = allocate_discount(keyed, discount)

    for line in alloc.lines:
        exact = line.line_total_paise * discount / subtotal
        assert abs(line.discount_alloc_paise - exact) < 1.0
