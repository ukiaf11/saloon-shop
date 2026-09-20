"""Content write services: versioning and cache invalidation."""

from __future__ import annotations

import pytest
from django.core.cache import cache

from apps.accounts.models import AdminUser, Role
from apps.content.models import LegalPage, SiteContent
from apps.content.services import publish_legal_page, set_site_content
from common.cache import KEY_SALON, legal_key

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor(db):
    return AdminUser.objects.create_user(
        email="owner@example.test",
        password=None,
        full_name="Salon Owner",
        role=Role.OWNER,
    )


def test_publish_creates_a_new_version_rather_than_editing(salon, actor):
    first = publish_legal_page(salon, "promotion-rules", "Promotion Rules", "v1 body", actor)
    second = publish_legal_page(salon, "promotion-rules", "Promotion Rules", "v2 body", actor)

    assert (first.version, second.version) == (1, 2)
    first.refresh_from_db()
    assert first.body_markdown == "v1 body", "the earlier version must stay recoverable"
    assert LegalPage.objects.filter(salon=salon, slug="promotion-rules").count() == 2


def test_publish_records_publisher_and_timestamp(salon, actor):
    page = publish_legal_page(salon, "terms", "Terms", "body", actor)
    assert page.published_at is not None
    assert page.published_by == actor


def test_publish_versions_are_independent_per_slug(salon, actor):
    publish_legal_page(salon, "terms", "Terms", "body", actor)
    publish_legal_page(salon, "terms", "Terms", "body 2", actor)
    privacy = publish_legal_page(salon, "privacy", "Privacy", "body", actor)
    assert privacy.version == 1


def test_publish_invalidates_only_its_own_legal_key(
    salon, actor, django_capture_on_commit_callbacks
):
    cache.set(legal_key("terms"), {"stale": True}, 60)
    cache.set(legal_key("privacy"), {"stale": True}, 60)

    with django_capture_on_commit_callbacks(execute=True):
        publish_legal_page(salon, "terms", "Terms", "body", actor)

    assert cache.get(legal_key("terms")) is None
    assert cache.get(legal_key("privacy")) == {"stale": True}


def test_set_site_content_upserts_and_invalidates_the_salon_payload(
    salon, actor, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        set_site_content(salon, "hero_heading", "Har Din 5 Lucky Slots", actor)

    cache.set(KEY_SALON, {"stale": True}, 60)
    with django_capture_on_commit_callbacks(execute=True):
        updated = set_site_content(salon, "hero_heading", "New heading", actor)

    assert cache.get(KEY_SALON) is None
    assert SiteContent.objects.filter(salon=salon, key="hero_heading").count() == 1
    assert updated.value == "New heading"
    assert updated.updated_by == actor


def test_set_site_content_stores_structured_values(salon):
    content = set_site_content(salon, "social_links", {"instagram": None, "facebook": None})
    content.refresh_from_db()
    assert content.value == {"instagram": None, "facebook": None}
