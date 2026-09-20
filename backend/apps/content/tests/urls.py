"""URLconf used by the content tests.

The app's routes are mounted into config/api_urls.py centrally, so the tests
mount them here at the same prefix the contract documents and select this
module with @pytest.mark.urls.
"""

from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("apps.content.urls")),
]
