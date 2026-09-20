"""Per-request context, available to logging and audit without threading it
through every function signature."""

from __future__ import annotations

import contextvars

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
actor_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("actor_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


def get_actor_id() -> str | None:
    return actor_id_var.get()
