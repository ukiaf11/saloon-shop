"""Model-level guarantees for the content app."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

# Imported as a module, not by name: pytest's default `python_classes = Test*`
# would otherwise try to collect the Testimonial model as a test class.
from apps.content import models

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_check_constraint_rejects_out_of_range(salon, rating):
    """The 1..5 bound is enforced by the database, not only by a validator."""
    with pytest.raises(IntegrityError), transaction.atomic():
        models.Testimonial.objects.create(salon=salon, author_name="A.", rating=rating, body="...")


@pytest.mark.parametrize("rating", [1, 3, 5])
def test_rating_check_constraint_accepts_the_range(salon, rating):
    testimonial = models.Testimonial.objects.create(
        salon=salon, author_name="A.", rating=rating, body="..."
    )
    assert testimonial.rating == rating


def test_alt_text_is_required(salon, png_upload):
    """Accessibility requirement: a gallery photo without a description is invalid."""
    image = models.GalleryImage(salon=salon, image=png_upload(), alt_text="")
    with pytest.raises(ValidationError) as exc:
        image.full_clean()
    assert "alt_text" in exc.value.message_dict


def test_dimensions_are_populated_on_save(salon, png_upload):
    image = models.GalleryImage.objects.create(
        salon=salon, image=png_upload(size=(640, 480)), alt_text="Front desk"
    )
    assert (image.width, image.height) == (640, 480)


def test_legal_page_version_is_unique_per_slug(salon):
    models.LegalPage.objects.create(
        salon=salon, slug=models.LegalPage.Slug.TERMS, title="Terms", body_markdown="v1", version=1
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        models.LegalPage.objects.create(
            salon=salon,
            slug=models.LegalPage.Slug.TERMS,
            title="Terms",
            body_markdown="dup",
            version=1,
        )


def test_legal_page_versions_coexist_across_slugs(salon):
    """Versions are per document: publishing terms must not bump privacy."""
    for slug in (models.LegalPage.Slug.TERMS, models.LegalPage.Slug.PRIVACY):
        models.LegalPage.objects.create(
            salon=salon, slug=slug, title=slug.label, body_markdown="v1", version=1
        )
    assert models.LegalPage.objects.filter(version=1).count() == 2
