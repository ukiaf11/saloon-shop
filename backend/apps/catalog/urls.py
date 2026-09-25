"""Catalog routes. Mounted under /api/v1/ by config.api_urls."""

from django.urls import path

from apps.catalog import views

urlpatterns = [
    path("services", views.ServicesView.as_view(), name="services"),
    # Owner/manager catalogue management (API_CONTRACT_OWNER_CATALOG.md).
    path("owner/services", views.OwnerServicesView.as_view(), name="owner-services"),
    path(
        "owner/services/<uuid:service_id>/price",
        views.OwnerServicePriceView.as_view(),
        name="owner-service-price",
    ),
    path(
        "owner/services/<uuid:service_id>",
        views.OwnerServiceUpdateView.as_view(),
        name="owner-service-update",
    ),
]
