from __future__ import annotations

import io

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.content.models import FaqItem, GalleryImage, Testimonial
from apps.salons.models import Salon


@pytest.fixture(autouse=True)
def isolated_cache(settings, tmp_path):
    """Run against a private in-memory cache and a throwaway media root.

    These tests assert on cache state, so sharing the developer's Redis
    instance would make them order-dependent and destructive.
    """
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "content-tests",
        }
    }
    settings.MEDIA_ROOT = str(tmp_path / "media")
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def salon(db):
    return Salon.objects.create(name="Test Salon", slug="test-salon")


@pytest.fixture
def png_upload():
    """Real PNG bytes, so image validation and dimension reading both run."""

    def _make(name: str = "photo.png", size: tuple[int, int] = (400, 300)):
        buffer = io.BytesIO()
        Image.new("RGB", size, "white").save(buffer, format="PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

    return _make


@pytest.fixture
def gallery_image(salon, png_upload):
    return GalleryImage.objects.create(
        salon=salon,
        image=png_upload(),
        alt_text="Styling chair at the salon",
        caption="Our main floor",
        display_order=1,
    )


@pytest.fixture
def testimonial(salon):
    return Testimonial.objects.create(
        salon=salon,
        author_name="Rahul S.",
        rating=5,
        body="Best haircut in town.",
        is_published=True,
        display_order=1,
    )


@pytest.fixture
def faq(salon):
    return FaqItem.objects.create(
        salon=salon,
        question="How does the lucky slot work?",
        answer="Each day a fixed number of slots is generated in advance.",
        is_published=True,
        display_order=1,
    )
