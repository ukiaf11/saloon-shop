"""Money primitives.

Every monetary value in this system is an integer number of paise. Floats are
never used anywhere in the money path -- see REQUIREMENTS.md section 2.1.

The allocator in this module is load-bearing: its output is persisted on
``OrderItem.discount_alloc_paise`` and a winner's refund is computed from the
resulting ``net_paid_paise``. An off-by-one paise here becomes a reconciliation
break against the payment gateway, so the invariants are asserted, not assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Allocation",
    "AllocationLine",
    "Paise",
    "allocate_discount",
    "format_inr",
    "percent_of",
]

Paise = int


class MoneyError(ValueError):
    """Raised when a money operation would violate an invariant."""


def _group_indian(n: int) -> str:
    """Indian digit grouping: 1234567 -> '12,34,567' (last 3, then pairs)."""
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def format_inr(paise: Paise) -> str:
    """Render paise for display only. Never feed this back into arithmetic.

    Uses Indian digit grouping (lakh/crore), not Western thousands.
    """
    if paise < 0:
        return f"-{format_inr(-paise)}"
    rupees, remainder = divmod(paise, 100)
    grouped = _group_indian(rupees)
    return f"₹{grouped}" if remainder == 0 else f"₹{grouped}.{remainder:02d}"


def percent_of(amount_paise: Paise, percent: int) -> Paise:
    """Integer percentage, truncated toward zero.

    Truncation (rather than rounding up) keeps the discount from ever exceeding
    the stated percentage, which is the customer-safe direction for a discount.
    """
    if amount_paise < 0:
        raise MoneyError("amount_paise must be non-negative")
    if not 0 <= percent <= 100:
        raise MoneyError("percent must be between 0 and 100")
    return (amount_paise * percent) // 100


@dataclass(frozen=True)
class AllocationLine:
    """One order line's share of an order-level discount."""

    key: str
    line_total_paise: Paise
    discount_alloc_paise: Paise

    @property
    def net_paid_paise(self) -> Paise:
        return self.line_total_paise - self.discount_alloc_paise


@dataclass(frozen=True)
class Allocation:
    lines: tuple[AllocationLine, ...]
    subtotal_paise: Paise
    discount_paise: Paise

    @property
    def total_paise(self) -> Paise:
        return self.subtotal_paise - self.discount_paise

    def by_key(self, key: str) -> AllocationLine:
        for line in self.lines:
            if line.key == key:
                return line
        raise KeyError(key)


def allocate_discount(
    lines: list[tuple[str, Paise]],
    discount_paise: Paise,
) -> Allocation:
    """Distribute an order-level discount across lines by largest remainder.

    ``lines`` is a list of ``(key, line_total_paise)``. ``key`` is the stable
    identifier used for the tie-break -- in production this is the
    ``order_item.id``, so the allocation is reproducible for any order.

    Algorithm (REQUIREMENTS.md section 8.3):

    1. exact proportional share = line_total * discount / subtotal
    2. floor each share to whole paise
    3. hand the leftover paise out one at a time, largest fractional remainder
       first, tie-broken on ``key`` ascending

    Guarantees, all asserted before returning:

    * ``sum(discount_alloc_paise) == discount_paise``
    * ``sum(net_paid_paise) == subtotal_paise - discount_paise``
    * ``0 <= discount_alloc_paise <= line_total_paise`` for every line
    """
    if discount_paise < 0:
        raise MoneyError("discount_paise must be non-negative")
    for key, line_total in lines:
        if line_total < 0:
            raise MoneyError(f"line {key!r} has negative line_total_paise")

    subtotal_paise = sum(line_total for _, line_total in lines)

    if discount_paise > subtotal_paise:
        raise MoneyError("discount_paise cannot exceed subtotal_paise")

    if not lines:
        if discount_paise:
            raise MoneyError("cannot allocate a discount across zero lines")
        return Allocation(lines=(), subtotal_paise=0, discount_paise=0)

    if subtotal_paise == 0 or discount_paise == 0:
        allocated = [AllocationLine(key, total, 0) for key, total in lines]
        return Allocation(tuple(allocated), subtotal_paise, discount_paise)

    # Step 1 + 2: exact share, floored. Kept in integers throughout --
    # numerator // subtotal is the floor, numerator % subtotal is the
    # fractional remainder scaled by subtotal, which is all the ordering needs.
    floors: list[Paise] = []
    remainders: list[int] = []
    for _, line_total in lines:
        numerator = line_total * discount_paise
        floors.append(numerator // subtotal_paise)
        remainders.append(numerator % subtotal_paise)

    leftover = discount_paise - sum(floors)

    # Step 3: largest remainder first, then key ascending for determinism.
    order = sorted(
        range(len(lines)),
        key=lambda i: (-remainders[i], lines[i][0]),
    )
    for i in order[:leftover]:
        floors[i] += 1

    allocated = tuple(
        AllocationLine(key, line_total, floors[i]) for i, (key, line_total) in enumerate(lines)
    )

    # Invariants. These are the whole point of the module.
    if sum(line.discount_alloc_paise for line in allocated) != discount_paise:
        raise MoneyError("allocation does not sum to discount_paise")
    if sum(line.net_paid_paise for line in allocated) != subtotal_paise - discount_paise:
        raise MoneyError("net paid does not sum to total_paise")
    for line in allocated:
        if not 0 <= line.discount_alloc_paise <= line.line_total_paise:
            raise MoneyError(f"line {line.key!r} allocation out of range")

    return Allocation(allocated, subtotal_paise, discount_paise)
