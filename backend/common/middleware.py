from __future__ import annotations

import uuid

from django.utils.deprecation import MiddlewareMixin

from common.context import actor_id_var, request_id_var

REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
RESPONSE_HEADER = "X-Request-ID"


class RequestIdMiddleware(MiddlewareMixin):
    """Attach a request id to every request, log line and audit record.

    An inbound X-Request-ID is honoured only when it looks like a UUID, so a
    caller cannot inject arbitrary text into our log stream.
    """

    def process_request(self, request) -> None:
        incoming = request.META.get(REQUEST_ID_HEADER, "")
        try:
            request_id = str(uuid.UUID(incoming))
        except (ValueError, AttributeError, TypeError):
            request_id = str(uuid.uuid4())

        request.request_id = request_id
        request_id_var.set(request_id)

        user = getattr(request, "user", None)
        actor_id_var.set(str(user.pk) if user and user.is_authenticated else None)

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", None)
        if request_id:
            response[RESPONSE_HEADER] = request_id
        return response
