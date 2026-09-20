"""Public content endpoints, checked against API_CONTRACT_PHASE2.md.

The payload key sets are asserted exactly: the frontend parses these with Zod,
so an extra field is a broken build and a missing one is a broken page.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache

# Imported as a module, not by name: pytest's default `python_classes = Test*`
# would otherwise try to collect the Testimonial model as a test class.
from apps.content import models
from apps.content.services import publish_legal_page
from common.cache import KEY_FAQS, KEY_GALLERY, KEY_TESTIMONIALS

pytestmark = [pytest.mark.django_db, pytest.mark.urls("apps.content.tests.urls")]

GALLERY_URL = "/api/v1/gallery"
TESTIMONIALS_URL = "/api/v1/testimonials"
FAQS_URL = "/api/v1/faqs"


# --- gallery -------------------------------------------------------------


def test_gallery_payload_matches_the_contract(client, gallery_image):
    response = client.get(GALLERY_URL)

    assert response.status_code == 200
    (row,) = response.json()["results"]
    assert set(row) == {
        "id",
        "image_url",
        "alt_text",
        "caption",
        "display_order",
        "width",
        "height",
    }
    assert row["alt_text"] == "Styling chair at the salon"
    assert row["caption"] == "Our main floor"
    assert (row["width"], row["height"]) == (400, 300)


def test_gallery_image_url_is_absolute(client, gallery_image):
    """next/image needs a resolvable URL; a storage-relative path will not do."""
    (row,) = client.get(GALLERY_URL).json()["results"]
    assert row["image_url"].startswith("http://testserver/")


def test_gallery_excludes_inactive_images(client, salon, gallery_image, png_upload):
    models.GalleryImage.objects.create(
        salon=salon, image=png_upload("hidden.png"), alt_text="Hidden", is_active=False
    )
    results = client.get(GALLERY_URL).json()["results"]
    assert [row["alt_text"] for row in results] == ["Styling chair at the salon"]


def test_gallery_is_ordered_by_display_order(client, salon, png_upload):
    for order, alt in ((2, "second"), (1, "first")):
        models.GalleryImage.objects.create(
            salon=salon, image=png_upload(f"{alt}.png"), alt_text=alt, display_order=order
        )
    results = client.get(GALLERY_URL).json()["results"]
    assert [row["alt_text"] for row in results] == ["first", "second"]


def test_gallery_is_public_and_unpaginated(client, gallery_image):
    body = client.get(GALLERY_URL).json()
    assert set(body) == {"results"}, "the contract has no pagination envelope"


# --- testimonials --------------------------------------------------------


def test_testimonials_payload_matches_the_contract(client, testimonial):
    (row,) = client.get(TESTIMONIALS_URL).json()["results"]
    assert set(row) == {"id", "author_name", "rating", "body", "display_order"}
    assert row["rating"] == 5


def test_testimonials_exclude_unpublished(client, salon, testimonial):
    models.Testimonial.objects.create(
        salon=salon, author_name="Draft", rating=1, body="...", is_published=False
    )
    results = client.get(TESTIMONIALS_URL).json()["results"]
    assert [row["author_name"] for row in results] == ["Rahul S."]


# --- faqs ----------------------------------------------------------------


def test_faqs_payload_matches_the_contract(client, faq):
    (row,) = client.get(FAQS_URL).json()["results"]
    assert set(row) == {"id", "question", "answer", "display_order"}


def test_faqs_exclude_unpublished(client, salon, faq):
    models.FaqItem.objects.create(salon=salon, question="Draft?", answer="...", is_published=False)
    results = client.get(FAQS_URL).json()["results"]
    assert [row["question"] for row in results] == ["How does the lucky slot work?"]


# --- legal ---------------------------------------------------------------


def test_legal_returns_the_latest_published_version(client, salon):
    publish_legal_page(salon, "promotion-rules", "Promotion Rules", "## v1", None)
    publish_legal_page(salon, "promotion-rules", "Promotion Rules", "## v2", None)

    body = client.get("/api/v1/legal/promotion-rules").json()

    assert set(body) == {"slug", "title", "body_markdown", "version", "published_at"}
    assert body["version"] == 2
    assert body["body_markdown"] == "## v2"


def test_legal_ignores_drafts(client, salon):
    """A seeded draft must never be served as if it were policy."""
    models.LegalPage.objects.create(
        salon=salon,
        slug=models.LegalPage.Slug.TERMS,
        title="Terms",
        body_markdown="AWAITING LEGAL SIGN-OFF",
        version=1,
        published_at=None,
    )

    response = client.get("/api/v1/legal/terms")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_legal_unpublished_slug_returns_not_found(client, salon):
    response = client.get("/api/v1/legal/privacy")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_legal_unknown_slug_returns_not_found(client, salon):
    response = client.get("/api/v1/legal/something-else")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_legal_is_visible_immediately_after_publishing(
    client, salon, django_capture_on_commit_callbacks
):
    """A published policy must not wait for a TTL: the cached miss is dropped."""
    assert client.get("/api/v1/legal/refunds").status_code == 404

    with django_capture_on_commit_callbacks(execute=True):
        publish_legal_page(salon, "refunds", "Refund Policy", "## Refunds", None)

    response = client.get("/api/v1/legal/refunds")
    assert response.status_code == 200
    assert response.json()["version"] == 1


# --- caching -------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "key"),
    [
        (GALLERY_URL, KEY_GALLERY),
        (TESTIMONIALS_URL, KEY_TESTIMONIALS),
        (FAQS_URL, KEY_FAQS),
    ],
)
def test_reads_populate_the_documented_cache_key(client, gallery_image, testimonial, faq, url, key):
    assert cache.get(key) is None
    client.get(url)
    assert cache.get(key) is not None


def test_saving_a_testimonial_drops_the_cached_payload(
    client, testimonial, django_capture_on_commit_callbacks
):
    client.get(TESTIMONIALS_URL)
    assert cache.get(KEY_TESTIMONIALS) is not None

    with django_capture_on_commit_callbacks(execute=True):
        testimonial.body = "Corrected wording."
        testimonial.save()

    assert cache.get(KEY_TESTIMONIALS) is None
    (row,) = client.get(TESTIMONIALS_URL).json()["results"]
    assert row["body"] == "Corrected wording."


def test_deleting_a_gallery_image_drops_the_cached_payload(
    client, gallery_image, django_capture_on_commit_callbacks
):
    client.get(GALLERY_URL)
    assert cache.get(KEY_GALLERY) is not None

    with django_capture_on_commit_callbacks(execute=True):
        gallery_image.delete()

    assert cache.get(KEY_GALLERY) is None
    assert client.get(GALLERY_URL).json()["results"] == []


def test_unpublishing_an_faq_removes_it_from_the_payload(
    client, faq, django_capture_on_commit_callbacks
):
    assert len(client.get(FAQS_URL).json()["results"]) == 1

    with django_capture_on_commit_callbacks(execute=True):
        faq.is_published = False
        faq.save()

    assert client.get(FAQS_URL).json()["results"] == []
