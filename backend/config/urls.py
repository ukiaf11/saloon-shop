from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import include, path


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("api/v1/", include("config.api_urls")),
]

if settings.DEBUG:
    # Local media serving only. In production, uploaded images are served from
    # object storage and this branch never runs.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
