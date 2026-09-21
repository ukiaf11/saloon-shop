"""Request helpers shared by views and audit."""

from __future__ import annotations

from django.conf import settings


def client_ip(request) -> str | None:
    """The caller's IP address.

    Behind Vercel, REMOTE_ADDR is the proxy and the client arrives in
    X-Real-IP, which the edge sets and overwrites. That header is trusted only
    when TRUST_X_REAL_IP says the deployment really sits behind such a proxy;
    anywhere else a client could send it and pick its own address, defeating
    the per-IP login limit.
    """
    if settings.TRUST_X_REAL_IP:
        forwarded = (request.META.get("HTTP_X_REAL_IP") or "").strip()
        if forwarded:
            return forwarded
    return request.META.get("REMOTE_ADDR") or None
