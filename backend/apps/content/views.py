"""Public content endpoints (API_CONTRACT_PHASE2.md).

These lists are small and the page renders them whole, so they are returned
unpaginated under a ``results`` key and cached in Redis with explicit
invalidation -- a corrected testimonial or a newly published policy has to be
visible on the next request, not after a TTL lapses.
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.content.models import FaqItem, GalleryImage, LegalPage, Testimonial
from apps.content.serializers import (
    FaqItemSerializer,
    GalleryImageSerializer,
    LegalPageSerializer,
    TestimonialSerializer,
)
from apps.salons.models import Salon
from common.cache import (
    KEY_FAQS,
    KEY_GALLERY,
    KEY_TESTIMONIALS,
    cached,
    legal_key,
)
from common.exceptions import NotFound


def _active_salon_id():
    """The salon these endpoints serve.

    V1 is single-salon and the public routes carry no salon selector, but every
    content row is already scoped by a salon FK (REQUIREMENTS.md 2.2). Resolving
    the salon here keeps that scoping real, so adding a second branch later is a
    routing change rather than a data-leak fix. Runs only on a cache miss.
    """
    return (
        Salon.objects.filter(status=Salon.Status.ACTIVE)
        .order_by("created_at")
        .values_list("id", flat=True)
        .first()
    )


def _rows(serializer) -> list[dict[str, Any]]:
    """Plain dicts, not DRF's ReturnList, because the result gets pickled into
    Redis and must not drag a serializer and its queryset along with it."""
    return [dict(row) for row in serializer.data]


def _build_gallery() -> dict[str, Any]:
    salon_id = _active_salon_id()
    if salon_id is None:
        return {"results": []}
    images = GalleryImage.objects.filter(salon_id=salon_id, is_active=True)
    return {"results": _rows(GalleryImageSerializer(images, many=True))}


def _build_testimonials() -> dict[str, Any]:
    salon_id = _active_salon_id()
    if salon_id is None:
        return {"results": []}
    testimonials = Testimonial.objects.filter(salon_id=salon_id, is_published=True)
    return {"results": _rows(TestimonialSerializer(testimonials, many=True))}


def _build_faqs() -> dict[str, Any]:
    salon_id = _active_salon_id()
    if salon_id is None:
        return {"results": []}
    faqs = FaqItem.objects.filter(salon_id=salon_id, is_published=True)
    return {"results": _rows(FaqItemSerializer(faqs, many=True))}


def _build_legal_page(slug: str) -> dict[str, Any]:
    """The latest published version, or an empty dict when there is none.

    Empty rather than ``None`` so the miss is cacheable: ``cached()`` reads
    ``None`` as "not in cache". Caching the negative is safe because
    ``services.publish_legal_page`` invalidates this key, so the first publish
    is visible immediately.
    """
    salon_id = _active_salon_id()
    if salon_id is None:
        return {}
    page = (
        LegalPage.objects.filter(salon_id=salon_id, slug=slug, published_at__isnull=False)
        .order_by("-version")
        .first()
    )
    return dict(LegalPageSerializer(page).data) if page else {}


class PublicContentView(APIView):
    """Base for the unauthenticated content reads.

    The project default permission is IsAuthenticated, so AllowAny has to be
    stated here or these endpoints 403 for the public site.
    """

    permission_classes = (AllowAny,)
    throttle_scope = "public_read"


class GalleryView(PublicContentView):
    def get(self, request):
        payload = cached(KEY_GALLERY, _build_gallery)
        # Absolutised per request rather than inside the builder, so no
        # hostname is ever baked into the shared cache.
        return Response(
            {
                "results": [
                    {**row, "image_url": request.build_absolute_uri(row["image_url"])}
                    if row.get("image_url")
                    else row
                    for row in payload["results"]
                ]
            }
        )


class TestimonialListView(PublicContentView):
    def get(self, request):
        return Response(cached(KEY_TESTIMONIALS, _build_testimonials))


class FaqListView(PublicContentView):
    def get(self, request):
        return Response(cached(KEY_FAQS, _build_faqs))


class LegalPageView(PublicContentView):
    def get(self, request, slug):
        if slug not in LegalPage.Slug.values:
            # Checked before the cache is touched: an unbounded slug would let
            # any caller mint arbitrary cache keys.
            raise NotFound("Unknown legal page.")

        payload = cached(legal_key(slug), lambda: _build_legal_page(slug))
        if not payload:
            raise NotFound("This page has not been published yet.")
        return Response(payload)
