"""Quote engine.

The discount boundary and the distinct-vs-quantity rule are the two places
where getting it wrong charges a real customer the wrong amount.
"""

from __future__ import annotations

import pytest

from apps.orders.services import (
    MAX_QUANTITY_PER_SERVICE,
    ServiceUnavailable,
    build_quote,
    normalise_items,
)
from apps.promotions.services import CampaignNotConfigured
from common.exceptions import ValidationFailed

pytestmark = pytest.mark.django_db


def items(*services_and_qty):
    return [{"service_id": str(s.id), "quantity": q} for s, q in services_and_qty]


# --- the discount boundary -----------------------------------------------


def test_one_distinct_service_gets_no_discount(salon, config, haircut):
    quote = build_quote(salon, items((haircut, 1)))
    assert quote.distinct_service_count == 1
    assert quote.eligible_for_discount is False
    assert quote.discount_paise == 0
    assert quote.discount_percent == 0  # not the configured 10
    assert quote.payable_paise == 30000


def test_two_distinct_services_unlock_the_discount(salon, config, haircut, shaving):
    quote = build_quote(salon, items((haircut, 1), (shaving, 1)))
    assert quote.distinct_service_count == 2
    assert quote.eligible_for_discount is True
    assert quote.subtotal_paise == 45000
    assert quote.discount_paise == 4500
    assert quote.payable_paise == 40500


def test_quantity_of_one_service_does_not_unlock_the_discount(salon, config, haircut):
    """Three haircuts is one service. Doc 1 section 3.2 is explicit that
    multiple units of the same service do not count as multiple services."""
    quote = build_quote(salon, items((haircut, 3)))
    assert quote.distinct_service_count == 1
    assert quote.eligible_for_discount is False
    assert quote.discount_paise == 0
    assert quote.subtotal_paise == 90000
    assert quote.payable_paise == 90000


def test_min_distinct_services_is_read_from_config(salon, config, haircut, shaving):
    config.min_distinct_services = 3
    config.save()
    quote = build_quote(salon, items((haircut, 1), (shaving, 1)))
    assert quote.eligible_for_discount is False
    assert quote.min_distinct_services == 3


# --- allocation invariants ------------------------------------------------


def test_allocation_sums_match_the_order_totals(salon, config, haircut, hair_spa):
    quote = build_quote(salon, items((haircut, 1), (hair_spa, 1)))
    assert sum(line.line_total_paise for line in quote.lines) == quote.subtotal_paise
    assert sum(line.discount_alloc_paise for line in quote.lines) == quote.discount_paise
    assert sum(line.net_paid_paise for line in quote.lines) == quote.payable_paise


def test_locked_worked_example_from_requirements(salon, config, haircut, hair_spa):
    """REQUIREMENTS.md 8.1: Haircut 300 + Hair Spa 800 at 10% -> 270 / 720."""
    quote = build_quote(salon, items((haircut, 1), (hair_spa, 1)))
    by_slug = {line.service.slug: line for line in quote.lines}
    assert by_slug["hair-cutting"].net_paid_paise == 27000
    assert by_slug["hair-spa"].net_paid_paise == 72000
    assert quote.payable_paise == 99000


def test_rounding_edge_leaves_no_stray_paise(salon, config, category):
    """A subtotal that does not divide evenly must still reconcile exactly."""
    from apps.orders.tests.conftest import _service

    a = _service(salon, category, "A", "a", 33333)
    b = _service(salon, category, "B", "b", 33333)
    c = _service(salon, category, "C", "c", 33334)

    quote = build_quote(salon, items((a, 1), (b, 1), (c, 1)))
    assert quote.subtotal_paise == 100000
    assert quote.discount_paise == 10000
    assert sum(line.discount_alloc_paise for line in quote.lines) == 10000
    assert sum(line.net_paid_paise for line in quote.lines) == 90000


# --- rejection ------------------------------------------------------------


def test_inactive_service_is_refused(salon, config, haircut, inactive_service):
    with pytest.raises(ServiceUnavailable):
        build_quote(salon, items((haircut, 1), (inactive_service, 1)))


def test_unknown_service_is_refused(salon, config, haircut):
    import uuid

    with pytest.raises(ServiceUnavailable):
        build_quote(
            salon,
            [
                {"service_id": str(haircut.id), "quantity": 1},
                {"service_id": str(uuid.uuid4()), "quantity": 1},
            ],
        )


def test_a_service_from_another_salon_is_refused(salon, config, category, haircut):
    from apps.orders.tests.conftest import _service
    from apps.salons.models import Salon

    other = Salon.objects.create(name="Other", slug="other")
    other_cat = category.__class__.objects.create(salon=other, name="X", slug="x")
    foreign = _service(other, other_cat, "Foreign", "foreign", 5000)

    with pytest.raises(ServiceUnavailable):
        build_quote(salon, items((haircut, 1), (foreign, 1)))


def test_missing_config_raises_rather_than_guessing(salon, haircut, shaving):
    """Inventing a discount percent would mean charging a number nobody set."""
    with pytest.raises(CampaignNotConfigured):
        build_quote(salon, items((haircut, 1), (shaving, 1)))


# --- item normalisation ---------------------------------------------------


def test_duplicate_service_ids_merge_by_summing_quantity():
    out = normalise_items([{"service_id": "a", "quantity": 1}, {"service_id": "a", "quantity": 2}])
    assert len(out) == 1
    assert out[0].quantity == 3


def test_quantity_defaults_to_one():
    assert normalise_items([{"service_id": "a"}])[0].quantity == 1


@pytest.mark.parametrize("bad", [0, -1, MAX_QUANTITY_PER_SERVICE + 1, "2", 1.5, True])
def test_bad_quantity_is_refused(bad):
    with pytest.raises(ValidationFailed):
        normalise_items([{"service_id": "a", "quantity": bad}])


def test_merged_quantity_cannot_exceed_the_cap():
    with pytest.raises(ValidationFailed):
        normalise_items([{"service_id": "a", "quantity": 6}, {"service_id": "a", "quantity": 6}])


def test_empty_basket_is_refused():
    with pytest.raises(ValidationFailed):
        normalise_items([])


def test_configured_rate_is_reported_even_when_not_applied(salon, config, haircut):
    """The UI needs the number to say "add 1 more to unlock 10% off", without
    implying the discount is already on the total."""
    quote = build_quote(salon, items((haircut, 1)))
    assert quote.eligible_for_discount is False
    assert quote.discount_percent == 0
    assert quote.configured_discount_percent == 10
    assert quote.discount_paise == 0
