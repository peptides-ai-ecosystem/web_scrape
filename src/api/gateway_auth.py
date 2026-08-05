"""Gateway token authentication for API routes.

The orchestrator gateway forwards requests to this service and presents the
shared upstream secret (``API_TOKEN``) in the ``GATEWAY_AUTH_HEADER`` header
(``X-Gateway-Token`` by default). This dependency verifies that header on the
``/api/v1`` router.

Local development without a gateway: leave ``API_TOKEN`` empty and the check
is skipped, preserving the original open API behavior.
"""
import hmac
from fastapi import Header, HTTPException

from src.config import API_TOKEN, GATEWAY_AUTH_HEADER


def require_gateway_token(
    x_gateway_token: str | None = Header(default=None, alias=GATEWAY_AUTH_HEADER),
) -> None:
    if not API_TOKEN:
        return
    if not x_gateway_token or not hmac.compare_digest(x_gateway_token, API_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing gateway token.",
        )
