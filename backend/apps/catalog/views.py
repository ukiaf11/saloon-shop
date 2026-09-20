"""Public catalogue endpoint."""

from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.services import build_services_payload
from common.cache import KEY_SERVICES, cached


class ServicesView(APIView):
    """``GET /api/v1/services`` -- the whole active catalogue in one payload.

    Not paginated: the list is small, the page renders it whole, and a
    paginated envelope would break the contract the frontend validates against.
    The project default permission is IsAuthenticated, so AllowAny is set
    explicitly here rather than inherited.
    """

    permission_classes = (AllowAny,)
    throttle_scope = "public_read"

    def get(self, request):
        payload = cached(KEY_SERVICES, build_services_payload)
        return Response(_absolutise_image_urls(payload, request))


def _absolutise_image_urls(payload: dict, request) -> dict:
    """Expand storage URLs to absolute ones for this request's host.

    Done after the cache read, not before it: one cached payload serves every
    host. ``build_absolute_uri`` leaves an already-absolute URL (object
    storage, CDN) untouched.
    """
    if request is None:
        return payload
    results = [
        {**item, "image_url": request.build_absolute_uri(item["image_url"])}
        if item.get("image_url")
        else item
        for item in payload["results"]
    ]
    return {**payload, "results": results}
