"""URLconf for the catalogue API tests.

config.api_urls is wired up centrally, so the tests mount the app's own
urlpatterns rather than depending on that wiring having happened.
"""

from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("apps.catalog.urls")),
]
