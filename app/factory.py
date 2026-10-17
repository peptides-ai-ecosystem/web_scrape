"""Build the web_scrape FastAPI app: logging, Sentry, lifespan, middleware,
exception handlers, the ``/visualization`` dashboard mount and the routers.

``main.py`` only does ``app = create_app()``; the container runs
``uvicorn main:app``.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import openapi_docs
from app.api.v1.routers import api_router
from app.core.config import (
    START_SCHEDULER,
    VENDOR_SCHEMA_AUTO_CREATE,
    VENDOR_SCRAPE_CRON_ENABLED,
    VENDOR_SCRAPE_CRON_HOUR,
    VENDOR_SCRAPE_CRON_MINUTE,
)
from app.core.logging import setup_logging
from app.core.request_context import TraceContextMiddleware, bound_trace, trace_ids_from_request
from app.core.scheduler import shutdown_scheduler, start_scheduler, start_vendor_scrape_scheduler
from app.core.sentry import capture_exception, init_sentry

logger = logging.getLogger(__name__)

# The operator dashboard (static HTML/JS), served at /visualization.
VISUALIZATION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualization")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the pool on startup so the first request isn't slow
    from app.infrastructure.db.pool import get_pool

    get_pool()

    # Start the automated scheduler for background sync tasks
    if START_SCHEDULER:
        start_scheduler()
        logger.info("Scheduler started on boot (START_SCHEDULER=true)")
    else:
        logger.info("Scheduler start skipped on boot (START_SCHEDULER=false)")

    # Alembic revisions for this service's own tables, only when explicitly
    # enabled (the deploy normally runs `alembic upgrade head` itself).
    # Non-fatal: a failure is logged and the rest of the service still boots.
    if VENDOR_SCHEMA_AUTO_CREATE:
        from app.infrastructure.db.migrate import upgrade_to_head

        upgrade_to_head()

    # Nightly competitor price scrape (peptides-platform#288). Opt-in per
    # environment: we do not start hitting other companies' sites just
    # because someone booted the service.
    if VENDOR_SCRAPE_CRON_ENABLED:
        start_vendor_scrape_scheduler(hour=VENDOR_SCRAPE_CRON_HOUR, minute=VENDOR_SCRAPE_CRON_MINUTE)
        logger.info(
            "Nightly vendor scrape scheduled at %02d:%02d (VENDOR_SCRAPE_CRON_ENABLED=true)",
            VENDOR_SCRAPE_CRON_HOUR,
            VENDOR_SCRAPE_CRON_MINUTE,
        )
    else:
        logger.info("Nightly vendor scrape not scheduled (VENDOR_SCRAPE_CRON_ENABLED=false)")

    yield

    # Stop the automated scheduler cleanly on shutdown
    shutdown_scheduler()

    # Close all pool connections cleanly on shutdown
    from app.infrastructure.db.pool import close_pool

    close_pool()


# ---------------------------------------------------------------------------
# Global exception handling — any unhandled error returns clean JSON (500)
# instead of a bare traceback, so clients always get a parseable response.
# ---------------------------------------------------------------------------


def _route_tag(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Unchanged response; a 5xx is additionally reported to Sentry.

    Endpoints wrap failures as HTTPException(500, ...) inside ``except``, so
    the original error is ``exc.__context__`` — that is what gets captured.
    Ordinary 4xx is never reported.
    """
    if exc.status_code >= 500:
        capture_exception(exc.__context__ or exc, status_code=exc.status_code, route=_route_tag(request))
    return await default_http_exception_handler(request, exc)


async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id, request_id = trace_ids_from_request(request)
    logger.error(
        "Unhandled exception on %s %s (trace_id=%s): %s",
        request.method,
        request.url.path,
        trace_id,
        exc,
        exc_info=True,
    )
    # This handler runs outside every user middleware, so the request's trace
    # is re-bound from request.state for the Sentry event.
    with bound_trace(trace_id, request_id) as bound_id:
        capture_exception(exc, status_code=500, route=_route_tag(request))
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error. Check the server logs for details.",
            "path": request.url.path,
            "trace_id": bound_id,
        },
        headers={"X-Trace-Id": bound_id},
    )


# ---------------------------------------------------------------------------
# App-level routes (outside the gateway-token router)
# ---------------------------------------------------------------------------


async def home():
    """Home page with information and links."""
    return HTMLResponse(openapi_docs.HOME_HTML)


async def health():
    """Liveness probe for the orchestrator gateway and load balancers.

    Lightweight — returns 200 whenever the process is up and serving. The
    gateway aggregates this as ``{base_url}/health``.

    FEEDBACK-3 G36: ``commit`` is the git sha the running image was built from
    (the deploy workflow's ``GIT_SHA`` build arg). The EC2 host runs a pulled
    image and holds no source, so this is how to tell which code is live.
    """
    return {"status": "healthy", "service": "web_scrape", "commit": os.getenv("GIT_SHA") or "unknown"}


def create_app() -> FastAPI:
    """The configured application. Logging and Sentry are set up first."""
    setup_logging(log_dir=os.getenv("LOG_DIR", "log"))
    # FEEDBACK-3 G15: before the app is built, so an exception during construction
    # is reported. A no-op when SENTRY_DSN is empty: sentry_sdk.init is not called.
    init_sentry()

    app = FastAPI(
        title=openapi_docs.TITLE,
        description=openapi_docs.DESCRIPTION,
        version=openapi_docs.VERSION,
        lifespan=lifespan,
        contact=openapi_docs.CONTACT,
        license_info=openapi_docs.LICENSE_INFO,
        openapi_tags=openapi_docs.OPENAPI_TAGS,
    )

    # Reads (or mints) X-Trace-Id and echoes it, so a Sentry event and the
    # gateway's log lines for the same request share one id (FEEDBACK-3 G15).
    app.add_middleware(TraceContextMiddleware)

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Mount static files for visualization
    if os.path.exists(VISUALIZATION_DIR):
        app.mount("/visualization", StaticFiles(directory=VISUALIZATION_DIR, html=True), name="visualization")

    # Include all the API endpoints
    app.include_router(api_router, prefix="/api/v1")

    app.add_api_route("/", home, methods=["GET"])
    app.add_api_route("/health", health, methods=["GET"], tags=["Operations"])

    @app.get("/api/v1/openapi.json", include_in_schema=False)
    async def prefixed_openapi():
        """Serve the OpenAPI schema at the gateway-expected path.

        The orchestrator gateway fetches ``{base_url}/api/v1/openapi.json`` to
        render per-service docs (see docs/adding-a-microservice.md — upstream
        contract). FastAPI only exposes the schema at the app root
        (``/openapi.json``), so alias it here. Registered on the app (not the
        ``api_router``) because the gateway's docs fetch presents no gateway
        token.
        """
        return JSONResponse(app.openapi())

    return app
