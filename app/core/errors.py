"""Typed errors that services and controllers raise instead of HTTP exceptions.

Services must not import FastAPI. They raise one of these; the endpoint maps it
to an ``HTTPException`` with the same status code and ``detail`` text
(``app.api.errors.http_error``), so responses stay byte-identical.
"""


class ServiceError(Exception):
    """Base class. ``status_code`` is the HTTP status the endpoint returns."""

    status_code = 500

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadRequestError(ServiceError):
    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


class InvalidInputError(ServiceError):
    status_code = 422


class ServiceUnavailableError(ServiceError):
    status_code = 503


class ConfigurationError(ServiceError):
    """A required setting (e.g. ``DATABASE_URL``) is missing on the server."""

    status_code = 500
