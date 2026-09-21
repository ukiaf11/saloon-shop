"""v1 API routes.

Each app owns its own urls module with no prefix; they are mounted here under
/api/v1/. Apps are added as their phase lands.
"""

from django.urls import include, path

from common.cron import daily_rollover
from common.views import readiness

urlpatterns = [
    path("readiness", readiness, name="readiness"),
    # Called by Vercel Cron; authenticated by CRON_SECRET (see common/cron.py).
    path("internal/cron/daily-rollover", daily_rollover, name="cron-daily-rollover"),
    # Phase 2 -- public read endpoints (catalog + content + salon profile).
    path("", include("apps.salons.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.content.urls")),
    # Phase 3 -- quote and order engine.
    path("", include("apps.orders.urls")),
    # Phase 4 -- daily campaign.
    path("", include("apps.promotions.urls")),
]
