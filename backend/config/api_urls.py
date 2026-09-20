"""v1 API routes.

Each app owns its own urls module with no prefix; they are mounted here under
/api/v1/. Apps are added as their phase lands.
"""

from django.urls import include, path

from common.views import readiness

urlpatterns = [
    path("readiness", readiness, name="readiness"),
    # Phase 2 -- public read endpoints (catalog + content + salon profile).
    path("", include("apps.salons.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.content.urls")),
]
