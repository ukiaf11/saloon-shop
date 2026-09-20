"""Fixtures for the public salon endpoint tests."""

from __future__ import annotations

import pytest
from django.apps import apps as django_apps
from django.db import connection

from apps.salons.models import Salon


@pytest.fixture
def salon(db) -> Salon:
    return Salon.objects.create(
        name="Upendra Salon",
        slug="upendra-salon",
        address="12 MG Road, Indore",
        phone="+919000000000",
        whatsapp="+919000000000",
        email="hello@example.com",
        maps_url="https://maps.google.com/?q=upendra-salon",
    )


@pytest.fixture
def no_cache(settings):
    """Serve every request from the database.

    A developer machine has a live Redis, and a payload cached by one test would
    otherwise be asserted on by the next.
    """
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}


@pytest.fixture
def site_content_model(db):
    """The content app's SiteContent model, or a skip.

    It is built in parallel with this endpoint, so its absence is an expected
    state of the tree rather than a failure of the salon payload.
    """
    try:
        model = django_apps.get_model("content", "SiteContent")
    except LookupError:
        pytest.skip("apps.content.SiteContent does not exist yet")

    if model._meta.db_table not in connection.introspection.table_names():
        pytest.skip("SiteContent has no migrated table yet")
    return model
