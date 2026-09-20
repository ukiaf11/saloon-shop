"""Content assembly: defaults, overrides, and degradation.

The content block is sourced from another app's key/value rows, so the two
things worth pinning down are that a fresh install still renders and that a
stored row genuinely wins over the fallback copy.
"""

from __future__ import annotations

import pytest
from django.db import ProgrammingError

from apps.salons import serializers as salon_serializers
from apps.salons.models import Salon
from apps.salons.serializers import CONTENT_KEYS, DEFAULT_CONTENT, content_for
from apps.salons.views import build_salon_payload

CONTRACT_CONTENT_KEYS = {
    "hero_eyebrow",
    "hero_heading",
    "hero_subheading",
    "why_choose_us",
    "social_links",
}


def test_defaults_cover_exactly_the_contract_keys():
    assert set(DEFAULT_CONTENT) == CONTRACT_CONTENT_KEYS
    assert set(CONTENT_KEYS) == CONTRACT_CONTENT_KEYS


@pytest.mark.django_db
def test_defaults_apply_when_no_rows_exist(salon):
    assert build_salon_payload()["content"] == DEFAULT_CONTENT


@pytest.mark.django_db
def test_returned_content_is_a_copy_of_the_defaults(salon):
    content = content_for(salon)
    content["hero_heading"] = "mutated"
    content["why_choose_us"].append({"title": "x", "body": "y"})

    assert DEFAULT_CONTENT["hero_heading"] != "mutated"
    assert len(DEFAULT_CONTENT["why_choose_us"]) == 3


@pytest.mark.django_db
def test_stored_rows_override_defaults_and_absent_keys_still_appear(salon, site_content_model):
    site_content_model.objects.create(salon=salon, key="hero_heading", value="Naya Look")
    site_content_model.objects.create(
        salon=salon,
        key="social_links",
        value={"instagram": "https://instagram.com/upendra", "facebook": None},
    )

    content = build_salon_payload()["content"]

    assert content["hero_heading"] == "Naya Look"
    assert content["social_links"]["instagram"] == "https://instagram.com/upendra"
    assert set(content) == CONTRACT_CONTENT_KEYS
    assert content["hero_eyebrow"] == DEFAULT_CONTENT["hero_eyebrow"]
    assert content["why_choose_us"] == DEFAULT_CONTENT["why_choose_us"]


@pytest.mark.django_db
def test_structured_rows_are_returned_verbatim(salon, site_content_model):
    reasons = [{"title": "Walk-ins welcome", "body": "No appointment needed."}]
    site_content_model.objects.create(salon=salon, key="why_choose_us", value=reasons)

    assert build_salon_payload()["content"]["why_choose_us"] == reasons


@pytest.mark.django_db
def test_keys_outside_the_contract_are_not_exposed(salon, site_content_model):
    site_content_model.objects.create(salon=salon, key="admin_note", value="internal")

    assert set(build_salon_payload()["content"]) == CONTRACT_CONTENT_KEYS


@pytest.mark.django_db
def test_null_row_value_falls_back_to_the_default(salon, monkeypatch):
    """A stored JSON null means "not configured", not "render nothing"."""

    class _Rows:
        def values_list(self, *fields):
            return [("hero_heading", None)]

    class _Manager:
        def filter(self, *args, **kwargs):
            return _Rows()

    class _NullValuedModel:
        objects = _Manager()

    monkeypatch.setattr(salon_serializers.apps, "get_model", lambda *a, **k: _NullValuedModel)

    assert content_for(salon)["hero_heading"] == DEFAULT_CONTENT["hero_heading"]


@pytest.mark.django_db
def test_another_salons_rows_do_not_leak(salon, site_content_model):
    other = Salon.objects.create(name="Other Salon", slug="other-salon")
    site_content_model.objects.create(salon=other, key="hero_heading", value="Wrong salon")

    assert content_for(salon)["hero_heading"] == DEFAULT_CONTENT["hero_heading"]


@pytest.mark.django_db
def test_missing_content_model_degrades_to_defaults(salon, monkeypatch):
    def unresolvable(*args, **kwargs):
        raise LookupError("content app is not installed")

    monkeypatch.setattr(salon_serializers.apps, "get_model", unresolvable)

    assert content_for(salon) == DEFAULT_CONTENT


@pytest.mark.django_db
def test_missing_content_table_degrades_to_defaults(salon, monkeypatch):
    class _UnmigratedManager:
        def filter(self, *args, **kwargs):
            raise ProgrammingError('relation "site_content" does not exist')

    class _UnmigratedModel:
        objects = _UnmigratedManager()

    monkeypatch.setattr(salon_serializers.apps, "get_model", lambda *a, **k: _UnmigratedModel)

    assert content_for(salon) == DEFAULT_CONTENT
    # The savepoint absorbed the failure, so the connection is still usable.
    assert build_salon_payload()["name"] == "Upendra Salon"
