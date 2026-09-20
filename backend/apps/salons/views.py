"""Public salon endpoint."""

from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.salons.models import Salon
from apps.salons.serializers import SalonSerializer
from common.cache import KEY_SALON, cached
from common.exceptions import NotFound


def build_salon_payload() -> dict:
    """Assemble the public salon payload from the database.

    Also the cache-miss builder, so an admin write only has to drop KEY_SALON
    and the next reader rebuilds from current data.
    """
    salon = (
        Salon.objects.filter(status=Salon.Status.ACTIVE)
        .prefetch_related("business_hours")
        .order_by("created_at")
        .first()
    )
    if salon is None:
        raise NotFound("Salon profile is not available.")

    # dict(): keep the cached value plain builtins rather than a ReturnDict that
    # drags the serializer into the pickle.
    return dict(SalonSerializer(salon).data)


class SalonView(APIView):
    """GET /salon -- profile, the full week of hours, and site copy.

    One cache key for the whole payload (public:salon:v1), matching the V1
    single-salon assumption the cache table in API_CONTRACT_PHASE2.md encodes.
    """

    permission_classes = (AllowAny,)
    throttle_scope = "public_read"

    def get(self, request):
        return Response(cached(KEY_SALON, build_salon_payload))
