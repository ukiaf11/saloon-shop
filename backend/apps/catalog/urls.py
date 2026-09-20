"""Catalog routes. Mounted under /api/v1/ by config.api_urls."""

from django.urls import path

from apps.catalog.views import ServicesView

urlpatterns = [
    path("services", ServicesView.as_view(), name="services"),
]
