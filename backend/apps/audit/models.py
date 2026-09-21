from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import UUIDModel


class AuditLog(UUIDModel):
    """One attributable staff action.

    Append-only: a row that could be edited afterwards would prove nothing, so
    `save` refuses updates and nothing in the app deletes these. `before` and
    `after` hold only what is needed to understand the change -- never a
    password, a token or image bytes.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    # Kept as text so the record still names who acted if the account goes.
    actor_email = models.EmailField(blank=True)
    action = models.CharField(max_length=64, db_index=True)
    entity_type = models.CharField(max_length=64, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

    def __str__(self) -> str:
        return f"{self.action} by {self.actor_email or 'system'}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Audit log entries are append-only.")
        super().save(*args, **kwargs)
