"""Public content serializers.

Field lists are pinned to API_CONTRACT_PHASE2.md and are deliberately explicit
rather than ``__all__``: the frontend validates these payloads with Zod, so an
accidentally added field is a broken build, and the contract is the place a new
field gets agreed.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.content.models import FaqItem, GalleryImage, LegalPage, Testimonial


class GalleryImageSerializer(serializers.ModelSerializer):
    # Storage-relative here; the view makes it absolute per request so that no
    # hostname is ever written into the shared cache.
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = GalleryImage
        fields = ("id", "image_url", "alt_text", "caption", "display_order", "width", "height")

    def get_image_url(self, obj: GalleryImage) -> str | None:
        try:
            return obj.image.url
        except ValueError:
            return None


class TestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = ("id", "author_name", "rating", "body", "display_order")


class FaqItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaqItem
        fields = ("id", "question", "answer", "display_order")


class LegalPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalPage
        fields = ("slug", "title", "body_markdown", "version", "published_at")
