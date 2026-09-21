from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.promotions.services import provision_campaign, public_progress
from apps.salons.models import Salon
from common.exceptions import NotFound


class PromotionTodayView(APIView):
    """GET /promotion/today -- the public campaign counters.

    Not cached. These numbers change with every payment and a stale count is
    exactly the kind of thing that makes a customer believe a slot is free when
    it is not.

    Provisions today's campaign if the scheduler has not yet: the first visitor
    of the day must not see an error because a cron job was late.
    """

    permission_classes = (AllowAny,)
    throttle_scope = "public_read"

    def get(self, request):
        salon = Salon.objects.filter(status=Salon.Status.ACTIVE).first()
        if salon is None:
            raise NotFound("Salon is not available.")

        campaign = provision_campaign(salon)
        return Response(public_progress(campaign))
