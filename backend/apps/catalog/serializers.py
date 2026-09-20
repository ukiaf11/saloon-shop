"""Public catalogue serialisers.

Shapes are fixed by API_CONTRACT_PHASE2.md. ``cost`` and price history are not
fields here and must never be added: the public payload is cached and served
unauthenticated.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Service, ServiceCategory


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ("id", "name", "slug", "display_order")


class NestedServiceCategorySerializer(serializers.ModelSerializer):
    """The category as embedded in a service row -- no display_order."""

    class Meta:
        model = ServiceCategory
        fields = ("id", "name", "slug")


class ServiceSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "price_paise",
            "duration_minutes",
            "image_url",
            "is_featured",
            "display_order",
            "category",
        )

    def get_image_url(self, service: Service) -> str | None:
        """Storage URL, or None. Made absolute at the view.

        Deliberately not absolutised here: this payload is cached under one
        key for every host, so baking in the host of whichever request missed
        the cache would serve the wrong origin to the others.
        """
        if not service.image:
            return None
        return service.image.url

    def get_category(self, service: Service) -> dict | None:
        category = service.category
        if category is None or not category.is_active:
            # An inactive category is absent from the payload's `categories`
            # list, so exposing its id here would give the frontend a filter
            # value it cannot resolve.
            return None
        # dict(): strip DRF's ReturnDict wrapper, which carries a back-reference
        # to the serializer and would be dragged into the Redis pickle.
        return dict(NestedServiceCategorySerializer(category).data)
