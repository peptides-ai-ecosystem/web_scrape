# XR-10 upstream (accepts the gateway X-Gateway-Token) — see orchestrator/docs/ecosystem/dependencies.md#xr-10
"""Gateway token authentication for API routes.

The orchestrator gateway forwards requests to this service and presents the
shared upstream secret (``API_TOKEN``) in the ``GATEWAY_AUTH_HEADER`` header
(``X-Gateway-Token`` by default). This dependency verifies that header on the
``/api/v1`` router.

Fail closed (MS:webscrape-3, the same posture as admin and peptide): while
``API_TOKEN`` is empty every API route answers 503 "authentication is not
configured", so a box that boots without its token never serves the API open.
The one opt-out is explicit local development: ``ALLOW_UNAUTHENTICATED=true``
together with ``ENVIRONMENT`` in ``local`` / ``dev`` / ``development``.
"""

import hmac
import logging

from fastapi import Header, HTTPException

from app.core.config import API_TOKEN, GATEWAY_AUTH_HEADER, settings

logger = logging.getLogger(__name__)

# ENVIRONMENT values that count as local development for ALLOW_UNAUTHENTICATED.
LOCAL_ENVIRONMENTS = frozenset({"local", "development", "dev"})

_warned_open = False


def _unauthenticated_allowed() -> bool:
    """True only for explicit local development: both switches must be set."""
    return bool(settings.ALLOW_UNAUTHENTICATED) and settings.ENVIRONMENT.strip().lower() in LOCAL_ENVIRONMENTS


def require_gateway_token(
    x_gateway_token: str | None = Header(default=None, alias=GATEWAY_AUTH_HEADER),
) -> None:
    global _warned_open
    if not API_TOKEN:
        if _unauthenticated_allowed():
            if not _warned_open:
                _warned_open = True
                logger.warning(
                    "API_TOKEN is not configured: gateway authentication is DISABLED "
                    "(ALLOW_UNAUTHENTICATED=true, local development only)"
                )
            return
        logger.critical("API_TOKEN is not configured; refusing API requests (503).")
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    if not x_gateway_token or not hmac.compare_digest(x_gateway_token, API_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing gateway token.",
        )
