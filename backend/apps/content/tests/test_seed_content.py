"""seed_content must be safe to re-run against a salon the owner has edited."""

from __future__ import annotations

import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

# Imported as a module, not by name: pytest's default `python_classes = Test*`
# would otherwise try to collect the Testimonial model as a test class.
from apps.content import models

pytestmark = pytest.mark.django_db

EXPECTED_KEYS = {
    "hero_eyebrow",
    "hero_heading",
    "hero_subheading",
    "why_choose_us",
    "social_links",
}


def _seed() -> None:
    call_command("seed_content", stdout=io.StringIO(), stderr=io.StringIO())


def test_seed_creates_the_contract_content_keys(salon):
    _seed()
    keys = set(models.SiteContent.objects.filter(salon=salon).values_list("key", flat=True))
    assert keys == EXPECTED_KEYS

    why = models.SiteContent.objects.get(salon=salon, key="why_choose_us").value
    assert all(set(card) == {"title", "body"} for card in why)
    assert set(models.SiteContent.objects.get(salon=salon, key="social_links").value) == {
        "instagram",
        "facebook",
    }


def test_seed_publishes_faqs(salon):
    _seed()
    assert models.FaqItem.objects.filter(salon=salon, is_published=True).count() >= 6


def test_sample_testimonials_are_never_published_by_the_seed(salon):
    """The seeded reviews are invented. Publishing them would put fake customer
    opinions on a real business's site, so they exist only for layout testing
    and stay unpublished until the owner replaces them with real ones."""
    _seed()
    assert models.Testimonial.objects.filter(salon=salon).count() >= 4
    assert models.Testimonial.objects.filter(salon=salon, is_published=True).count() == 0
    assert all(1 <= r <= 5 for r in models.Testimonial.objects.values_list("rating", flat=True))


def test_seeded_legal_pages_are_unpublished_placeholders(salon):
    """Nothing here is binding until the owner's counsel signs it off."""
    _seed()
    pages = models.LegalPage.objects.filter(salon=salon)
    assert set(pages.values_list("slug", flat=True)) == set(models.LegalPage.Slug.values)
    assert not pages.exclude(published_at=None).exists()
    assert all("AWAITING LEGAL SIGN-OFF" in page.body_markdown for page in pages)


def test_seed_is_idempotent_and_keeps_owner_edits(salon):
    _seed()
    heading = models.SiteContent.objects.get(salon=salon, key="hero_heading")
    heading.value = "Owner's own words"
    heading.save()

    _seed()

    heading.refresh_from_db()
    assert heading.value == "Owner's own words"
    assert models.SiteContent.objects.filter(salon=salon).count() == len(EXPECTED_KEYS)
    assert models.LegalPage.objects.filter(salon=salon).count() == len(models.LegalPage.Slug.values)


def test_seed_refuses_when_the_salon_is_ambiguous(salon):
    from apps.salons.models import Salon

    Salon.objects.create(name="Second Salon", slug="second-salon")
    with pytest.raises(CommandError):
        _seed()
