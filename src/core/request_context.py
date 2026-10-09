"""Per-request trace context (FEEDBACK-3 G15).

The orchestrator gateway mints ``X-Trace-Id`` and forwards it to every
upstream. This service had no use for it until Sentry: an event is only useful
if it can be matched to the gateway's log lines for the same request.

* :class:`TraceContextMiddleware` reads ``X-Trace-Id`` (or mints one when the
  request did not come through the gateway), mints a ``request_id``, binds both
  to context variables for the duration of the request, stores them on
  ``request.state`` and echoes ``X-Trace-Id`` on the response.
* :func:`bound_trace` binds a trace for work that has no HTTP request — a
  scheduler job or a scrape run — so its Sentry event carries its own id.
"""
from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

TRACE_HEADER = "x-trace-id"

trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# A trace id is echoed back in a header and written into Sentry tags, so an
# incoming one is accepted only if it is short and plain.
_SAFE_TRACE_ID = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")


def new_trace_id() -> str:
    return uuid.uuid4().hex


def get_trace_id() -> Optional[str]:
    return trace_id_var.get()


def get_request_id() -> Optional[str]:
    return request_id_var.get()


@contextmanager
def bound_trace(trace_id: Optional[str] = None, request_id: Optional[str] = None) -> Iterator[str]:
    """Bind ``trace_id`` (minted when None) for the duration of the block."""
    trace_id = trace_id or new_trace_id()
    t_token = trace_id_var.set(trace_id)
    r_token = request_id_var.set(request_id)
    try:
        yield trace_id
    finally:
        trace_id_var.reset(t_token)
        request_id_var.reset(r_token)


def trace_ids_from_request(request) -> tuple[Optional[str], Optional[str]]:
    """``(trace_id, request_id)`` for a request, from state or the header.

    The catch-all 500 handler runs in Starlette's ServerErrorMiddleware, which
    sits *outside* every user middleware, so by then the context variables have
    been reset; ``request.state`` still holds what the middleware recorded.
    """
    state = getattr(request, "state", None)
    trace_id = getattr(state, "trace_id", None) or request.headers.get(TRACE_HEADER)
    return trace_id, getattr(state, "request_id", None)


class TraceContextMiddleware:
    """Pure ASGI (not BaseHTTPMiddleware) so the bound context variables are
    visible to the endpoint, its dependencies and its BackgroundTasks."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers") or []:
            if name.lower() == TRACE_HEADER.encode():
                incoming = value.decode("latin-1").strip()
                break
        trace_id = incoming if incoming and _SAFE_TRACE_ID.match(incoming) else new_trace_id()
        request_id = new_trace_id()
        state = scope.setdefault("state", {})
        state["trace_id"] = trace_id
        state["request_id"] = request_id

        async def send_with_trace(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((b"x-trace-id", trace_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        with bound_trace(trace_id, request_id):
            await self.app(scope, receive, send_with_trace)
