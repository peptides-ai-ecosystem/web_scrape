"""Map the typed service errors (``app.core.errors``) to HTTP responses."""

from fastapi import HTTPException

from app.core.errors import ServiceError


def http_error(exc: ServiceError) -> HTTPException:
    """The ``HTTPException`` an endpoint raises for a service error: same status, same detail."""
    return HTTPException(status_code=exc.status_code, detail=exc.detail)
