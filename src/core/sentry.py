"""Sentry error capture for the web_scrape service (FEEDBACK-3 G15).

The deploy workflow could already write SENTRY_DSN into the box's .env; until
this module nothing read it. Same rules as the peptide service (M6), the chat
service (#111) and the orchestrator (DP-6):

1. **Empty DSN is a complete no-op.** ``SENTRY_DSN=""`` (the default) means
   ``sentry_sdk.init`` is never called: no client, no transport thread, no
   network call, and every ``capture_*`` helper returns immediately. That is
   the configuration the test suite and every local run use.
2. **No credential can reach Sentry.** ``include_local_variables=False`` stops
   frame locals — which in an ASGI app hold the raw request scope, headers
   included — from being attached at all. ``before_send`` then walks the whole
   event: sensitive keys by name (Authorization, X-Gateway-Token, API_TOKEN,
   DATABASE_URL, anything containing token / secret / password / api_key),
   ASGI ``[name, value]`` header pairs by their first element, and every string
   by literal and shape match (see ``src.core.redaction``). The SDK's own
   ``EventScrubber(recursive=True)`` runs behind it. **If scrubbing raises, the
   event is dropped** — an event nobody could prove clean is not sent.
3. **Errors are server-side failures, not client mistakes.** 5xx, timeouts and
   unhandled exceptions on HTTP routes are captured explicitly in ``main.py``.
   Ordinary 4xx is never an event. The SDK's own status-code capture and
   log-record capture are switched off so nothing is reported twice.
4. **Background work is captured too.** An APScheduler job that raises
   (:func:`capture_job_error`, an ``EVENT_JOB_ERROR`` listener) and a sync or
   competitor scrape run that fails as a whole
   (:func:`capture_background_failure`) each get an event under a freshly
   minted trace_id. A single competitor page that fails to parse is a log line
   inside the run, not an event.

Every event is tagged ``service=web_scrape`` plus ``trace_id`` (the incoming
``X-Trace-Id``) and ``request_id``, so one search finds the Sentry event and
the gateway's log lines for the same request.
"""
from __future__ import annotations

import logging
import os
import re
import socket
from typing import Any, Optional

from src.config import settings
from src.core.redaction import MASK, redact, secret_literals
from src.core.request_context import bound_trace, get_request_id, get_trace_id

logger = logging.getLogger(__name__)

SERVICE_NAME = "web_scrape"

# Field names whose *value* is always a credential. Compared after lowercasing
# and folding "-" to "_", so "X-Gateway-Token" matches "x_gateway_token".
_SENSITIVE_FIELDS = frozenset(
    {
        "authorization",
        "proxy_authorization",
        "x_gateway_token",
        "gateway_token",
        "x_api_key",
        "api_key",
        "api_token",
        "database_url",
        "sentry_dsn",
        "cookie",
        "set_cookie",
        "token",
        "secret",
        "password",
    }
)

# Any field name containing one of these is credential-bearing too.
_SENSITIVE_SUBSTRINGS = ("token", "secret", "password", "passwd", "api_key", "apikey", "authorization", "database_url")

# The repr of a bytes object, e.g. "b'authorization'" — how ASGI header names
# look once Sentry has stringified them.
_BYTES_REPR = re.compile(r"""^b(['"])(.*)\1$""", re.DOTALL)

_MAX_DEPTH = 20

_initialized = False


def is_enabled() -> bool:
    """True only when init actually ran against a configured DSN."""
    return _initialized


# ── scrubbing ────────────────────────────────────────────────────────────────


def _normalize(name: object) -> str:
    text = name.decode("latin-1", "replace") if isinstance(name, bytes) else str(name)
    text = text.strip()
    match = _BYTES_REPR.match(text)
    if match:
        text = match.group(2)
    return text.strip().lower().replace("-", "_")


def _is_sensitive_name(name: object) -> bool:
    if not isinstance(name, (str, bytes)):
        return False
    norm = _normalize(name)
    return norm in _SENSITIVE_FIELDS or any(part in norm for part in _SENSITIVE_SUBSTRINGS)


def _is_sensitive_pair(item: Any) -> bool:
    """``[b'authorization', b'Bearer …']`` — an ASGI header pair naming a credential."""
    return isinstance(item, (list, tuple)) and len(item) == 2 and _is_sensitive_name(item[0])


def _scrub(value: Any, literals: list[str], depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return value
    if isinstance(value, dict):
        return {k: (MASK if _is_sensitive_name(k) else _scrub(v, literals, depth + 1)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [
            [item[0], MASK] if _is_sensitive_pair(item) else _scrub(item, literals, depth + 1) for item in value
        ]
        return tuple(items) if isinstance(value, tuple) else items
    if isinstance(value, str):
        return redact(value, literals)
    if isinstance(value, bytes):
        return redact(value.decode("utf-8", "replace"), literals)
    return value


def scrub_event(event: dict[str, Any] | None) -> dict[str, Any] | None:
    """Remove credentials from an outgoing event. Pure, so it is testable
    against a hand-built event without a live client."""
    if event is None:
        return None
    request = event.get("request")
    if isinstance(request, dict):
        # Bodies and query strings are common accidental credential carriers
        # and are not needed to group an error.
        request.pop("data", None)
        request.pop("cookies", None)
        request.pop("query_string", None)
        if isinstance(request.get("url"), str):
            request["url"] = request["url"].partition("?")[0]
    scrubbed = _scrub(event, secret_literals())
    tags = scrubbed.setdefault("tags", {})
    if isinstance(tags, dict):
        for key, value in _context_tags().items():
            tags.setdefault(key, value)
    return scrubbed


def _before_send(event: Any, _hint: Any = None) -> Any:
    """Scrub and tag. Returning None drops the event — which is what happens
    if scrubbing itself raises."""
    try:
        return scrub_event(event)
    except Exception:
        logger.warning("Sentry before_send failed; dropping the event rather than sending it unscrubbed")
        return None


def _context_tags() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "trace_id": get_trace_id() or "-",
        "request_id": get_request_id() or "-",
    }


# ── init ─────────────────────────────────────────────────────────────────────


def _release() -> Optional[str]:
    explicit = settings.SENTRY_RELEASE.strip()
    if explicit:
        return explicit
    # The Dockerfile defaults GIT_SHA to "unknown" for a build without the arg.
    for var in ("GIT_SHA", "GITHUB_SHA"):
        value = (os.getenv(var) or "").strip()
        if value and value != "unknown":
            return value
    return None


def _environment() -> str:
    return settings.SENTRY_ENVIRONMENT.strip() or (os.getenv("ENVIRONMENT") or "").strip() or "production"


def init_sentry(**overrides: Any) -> bool:
    """Initialise Sentry if SENTRY_DSN is set. Returns whether it ran.

    ``overrides`` are passed to ``sentry_sdk.init`` after the defaults; the
    tests use it to install an in-process transport. A bad DSN or a missing
    extra logs a warning and leaves Sentry off — it never stops the boot.
    """
    global _initialized
    if _initialized:
        return True
    if not settings.SENTRY_DSN:
        logger.info("SENTRY_DSN not set — Sentry disabled (no init, no network calls)")
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

        options: dict[str, Any] = dict(
            dsn=settings.SENTRY_DSN,
            environment=_environment(),
            release=_release(),
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
            include_local_variables=False,
            max_request_body_size="never",
            event_scrubber=EventScrubber(denylist=[*DEFAULT_DENYLIST, *sorted(_SENSITIVE_FIELDS)], recursive=True),
            before_send=_before_send,
            integrations=[
                # No automatic capture by status code: 5xx is captured
                # explicitly (with context), 4xx never.
                StarletteIntegration(failed_request_status_codes=set()),
                FastApiIntegration(failed_request_status_codes=set()),
                # Log records become breadcrumbs, never events. log_error is
                # used for expected, handled conditions all over this service
                # (every competitor page that fails to parse, for one).
                LoggingIntegration(level=None, event_level=None),
            ],
        )
        options.update(overrides)
        sentry_sdk.init(**options)
        sentry_sdk.set_tag("service", SERVICE_NAME)
    except Exception as exc:
        logger.warning("Sentry init failed (continuing without it): %s", type(exc).__name__)
        return False
    _initialized = True
    logger.info("Sentry enabled (environment=%s, release=%s)", _environment(), _release() or "unset")
    return True


# ── capture helpers ──────────────────────────────────────────────────────────

_TIMEOUT_NAMES = frozenset(
    {"Timeout", "ReadTimeout", "ConnectTimeout", "TimeoutException", "TimeoutError", "PoolTimeout", "WriteTimeout"}
)


def is_timeout(exc: BaseException | None) -> bool:
    """A timeout from requests, Playwright, psycopg2, asyncio or a socket.

    Matched by class name across the MRO so this module does not have to
    import every client library to build an isinstance tuple.
    """
    seen = 0
    while exc is not None and seen < 5:
        if isinstance(exc, (TimeoutError, socket.timeout)):
            return True
        if any(k.__name__ in _TIMEOUT_NAMES for k in type(exc).__mro__):
            return True
        exc = exc.__cause__ or exc.__context__
        seen += 1
    return False


def capture_exception(
    exc: BaseException,
    *,
    status_code: int | None = None,
    fingerprint: list[str] | None = None,
    extras: dict[str, Any] | None = None,
    **tags: str,
) -> None:
    """Report a server-side failure with the current trace context.

    4xx is filtered here as well as at the call sites, so a caller cannot
    accidentally turn a client error into an event.
    """
    if not _initialized:
        return
    if status_code is not None and status_code < 500:
        return
    if getattr(exc, "_web_scrape_sentry_reported", False):
        return  # already reported where it happened, with better context
    try:
        import sentry_sdk

        timeout = is_timeout(exc)
        with sentry_sdk.new_scope() as scope:
            for key, value in _context_tags().items():
                scope.set_tag(key, value)
            if status_code is not None:
                scope.set_tag("status_code", str(status_code))
            scope.set_tag("timeout", "true" if timeout else "false")
            for key, value in tags.items():
                if value:
                    scope.set_tag(key, value)
            for key, value in (extras or {}).items():
                scope.set_extra(key, value)
            if fingerprint:
                scope.fingerprint = list(fingerprint)
            elif timeout:
                scope.fingerprint = ["timeout", type(exc).__name__, tags.get("route", "{{ default }}")]
            sentry_sdk.capture_exception(exc)
        try:
            exc._web_scrape_sentry_reported = True  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception as inner:
        logger.debug("Sentry capture failed (non-critical): %s", type(inner).__name__)


def capture_background_failure(exc: BaseException, *, job: str, **tags: str) -> str:
    """Report background work that failed as a whole, under its own trace_id.

    A sync or scrape run has no HTTP request of its own (the API-triggered
    scrape runs after its 202 has been sent), so it gets a freshly minted
    trace_id; the triggering request's id, if any, is kept as
    ``parent_trace_id``. Returns the minted id so the caller's log line can
    carry it. Always mints, even with Sentry off.
    """
    parent = get_trace_id()
    with bound_trace() as trace_id:
        capture_exception(exc, job=job, parent_trace_id=parent or "", **tags)
    return trace_id


def capture_job_error(event: Any) -> None:
    """APScheduler ``EVENT_JOB_ERROR`` listener: a job raised out of its body.

    ``event`` is a ``JobExecutionEvent``. Never raises — a listener that throws
    would be logged by APScheduler and nothing else.
    """
    exc = getattr(event, "exception", None)
    if exc is None or not _initialized:
        return
    try:
        capture_background_failure(exc, job=str(getattr(event, "job_id", "") or "unknown"), source="scheduler")
    except Exception as inner:
        logger.debug("Sentry job-error capture failed (non-critical): %s", type(inner).__name__)
