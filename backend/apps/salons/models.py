from __future__ import annotations

from django.db import models

from common.models import UUIDTimestampedModel


class Salon(UUIDTimestampedModel):
    """The salon. One row for V1.

    Every downstream table carries salon_id so multi-branch support is an
    additive change rather than a migration of the whole schema
    (REQUIREMENTS.md 8.4).
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    currency = models.CharField(max_length=3, default="INR")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    maps_url = models.URLField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "salon"

    def __str__(self) -> str:
        return self.name


class BusinessHour(UUIDTimestampedModel):
    class Day(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="business_hours")
    day_of_week = models.IntegerField(choices=Day.choices)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        db_table = "business_hour"
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "day_of_week"], name="uniq_business_hour_salon_day"
            ),
        ]
        ordering = ["day_of_week"]
