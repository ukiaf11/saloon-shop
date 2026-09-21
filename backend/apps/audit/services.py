"""Writing audit entries.

Call `record` inside the same transaction as the change it describes, so an
action and its audit entry commit or roll back together.
"""

from __future__ import annotations

from apps.audit.models import AuditLog
from common.context import get_request_id
from common.http import client_ip


def record(
    action: str,
    *,
    actor=None,
    entity=None,
    before: dict | None = None,
    after: dict | None = None,
    request=None,
) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor,
        actor_email=getattr(actor, "email", "") or "",
        action=action,
        entity_type=entity._meta.label_lower if entity is not None else "",
        entity_id=str(entity.pk) if entity is not None else "",
        before=before,
        after=after,
        ip_address=client_ip(request) if request is not None else None,
        request_id=get_request_id() or "",
    )
