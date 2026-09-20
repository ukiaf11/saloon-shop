"""Public salon profile serialization.

The payload is assembled rather than mapped one-to-one off the model: the week
is always seven days and the copy blocks live in the content app's key/value
rows, so both are normalised here to the shape in API_CONTRACT_PHASE2.md.
"""

from __future__ import annotations

import copy
import logging
from datetime import time

from django.apps import apps
from django.core.exceptions import FieldError
from django.db import DatabaseError, transaction
from rest_framework import serializers

from apps.salons.models import BusinessHour, Salon

logger = logging.getLogger(__name__)

# Copy served until the owner enters real content. These keys are never omitted
# from the response: the frontend renders the hero and the "why choose us" grid
# unconditionally, so a missing key would mean a blank section on a fresh
# install rather than a defaulted one. The heading wording is the recommended
# one (memory.md 4) and is editable from the admin without a deploy.
DEFAULT_CONTENT: dict[str, object] = {
    "hero_eyebrow": "Premium grooming. Daily rewards.",
    "hero_heading": "Har Din 5 Lucky Slots",
    "hero_subheading": "Hair Cutting + Shaving + Face Massage free for the day's lucky slots.",
    "why_choose_us": [
        {
            "title": "Trained stylists",
            "body": "Every service is delivered by an experienced, regularly trained stylist.",
        },
        {
            "title": "Hygiene first",
            "body": "Fresh tools and a sanitised station for every single customer.",
        },
        {
            "title": "Daily lucky rewards",
            "body": "Every paid visit automatically enters the day's lucky slots.",
        },
    ],
    "social_links": {"instagram": None, "facebook": None},
}

# Only these keys are read from SiteContent; the table also holds admin-facing
# and per-section copy that this endpoint has no business exposing.
CONTENT_KEYS = tuple(DEFAULT_CONTENT)

DAYS_IN_WEEK = 7

# Day names come from the model's own choices so there is one source of truth
# for the Monday(0) -> Sunday(6) ordering the contract mandates.
DAY_NAMES = {day.value: day.label for day in BusinessHour.Day}


def _clock(value: time | None, is_closed: bool) -> str | None:
    """Render a time as HH:MM. A closed day reports no times at all, even if a
    stale row still carries them -- the contract makes that a hard guarantee."""
    if is_closed or value is None:
        return None
    return value.strftime("%H:%M")


def week_for(salon: Salon) -> list[BusinessHour]:
    """Seven rows, Monday first.

    Days with no stored row are synthesised as closed (unsaved instances) so the
    frontend can render a complete week without null-checking, and so real and
    synthesised days go through one serialization path.
    """
    stored = {hour.day_of_week: hour for hour in salon.business_hours.all()}
    week = []
    for day in range(DAYS_IN_WEEK):
        hour = stored.get(day)
        if hour is None:
            hour = BusinessHour(salon=salon, day_of_week=day, is_closed=True)
        week.append(hour)
    return week


def content_for(salon: Salon) -> dict[str, object]:
    """Merge this salon's SiteContent rows over the defaults.

    The content app is resolved lazily: this endpoint must keep serving the
    salon profile even when that app is not yet migrated in, since the hours and
    contact details are the parts customers actually need.
    """
    content = copy.deepcopy(DEFAULT_CONTENT)

    try:
        site_content = apps.get_model("content", "SiteContent")
    except LookupError:
        logger.warning("site_content_model_unavailable")
        return content

    try:
        # Savepoint: if the table is not there yet, the failed query must not
        # leave an enclosing transaction broken for everything that follows.
        with transaction.atomic():
            rows = list(
                site_content.objects.filter(salon=salon, key__in=CONTENT_KEYS).values_list(
                    "key", "value"
                )
            )
    except (DatabaseError, FieldError):
        logger.warning("site_content_query_failed", exc_info=True)
        return content

    for key, value in rows:
        # A row explicitly set to JSON null means "not configured", not "blank".
        if value is not None:
            content[key] = value
    return content


class BusinessHourSerializer(serializers.ModelSerializer):
    day_name = serializers.SerializerMethodField()
    open_time = serializers.SerializerMethodField()
    close_time = serializers.SerializerMethodField()

    class Meta:
        model = BusinessHour
        fields = ("day_of_week", "day_name", "open_time", "close_time", "is_closed")

    def get_day_name(self, obj: BusinessHour) -> str:
        return DAY_NAMES[obj.day_of_week]

    def get_open_time(self, obj: BusinessHour) -> str | None:
        return _clock(obj.open_time, obj.is_closed)

    def get_close_time(self, obj: BusinessHour) -> str | None:
        return _clock(obj.close_time, obj.is_closed)


class SalonSerializer(serializers.ModelSerializer):
    """The public salon payload. Deliberately without `id` and `status`: the
    public site addresses the single salon implicitly and has no use for either."""

    business_hours = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()

    # API_CONTRACT_PHASE2.md: null means absent, never "". These are blank=True
    # CharFields on the model, so an unset one would otherwise serialize as an
    # empty string and force every consumer to test for both.
    OPTIONAL_TEXT_FIELDS = ("address", "phone", "whatsapp", "email", "maps_url")

    class Meta:
        model = Salon
        fields = (
            "name",
            "slug",
            "timezone",
            "currency",
            "address",
            "phone",
            "whatsapp",
            "email",
            "maps_url",
            "business_hours",
            "content",
        )

    def get_business_hours(self, obj: Salon) -> list[dict]:
        # list(): the payload is pickled into Redis, so it stays plain builtins
        # rather than a serializer-bound ReturnList.
        return list(BusinessHourSerializer(week_for(obj), many=True).data)

    def get_content(self, obj: Salon) -> dict:
        return content_for(obj)

    def to_representation(self, instance: Salon) -> dict:
        data = super().to_representation(instance)
        for field in self.OPTIONAL_TEXT_FIELDS:
            if not data.get(field):
                data[field] = None
        return data
