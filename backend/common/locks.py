"""Row-level locking helpers.

Capacity admission and coupon redemption both depend on holding a database row
lock for the duration of a transaction (REQUIREMENTS.md 3.4). These helpers
exist so that requirement is expressed the same way everywhere.
"""

from __future__ import annotations

from typing import TypeVar

from django.db import transaction

T = TypeVar("T")


def lock_row(queryset, **filters) -> T:
    """SELECT ... FOR UPDATE a single row. Must run inside a transaction."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("lock_row() must be called inside transaction.atomic()")
    return queryset.select_for_update().get(**filters)


def lock_row_or_none(queryset, **filters):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("lock_row_or_none() must be called inside transaction.atomic()")
    return queryset.select_for_update().filter(**filters).first()
