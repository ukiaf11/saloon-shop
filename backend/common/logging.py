from __future__ import annotations

import datetime as dt
import json
import logging

from common.context import get_actor_id, get_request_id
from common.masking import redact

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "asctime",
    "message",
    "taskName",
}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.actor_id = get_actor_id()
        return True


class JsonFormatter(logging.Formatter):
    """Structured logs. Extras are redacted before serialisation, so a careless
    ``logger.info(..., extra={"payload": webhook_body})`` cannot leak secrets."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": dt.datetime.fromtimestamp(record.created, tz=dt.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "actor_id": getattr(record, "actor_id", None),
        }

        extras = {k: v for k, v in record.__dict__.items() if k not in _RESERVED}
        extras.pop("request_id", None)
        extras.pop("actor_id", None)
        if extras:
            payload.update(redact(extras))

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)
