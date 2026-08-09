"""A single error envelope, so the generated TypeScript client has one shape to handle."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base class for errors that map to a deliberate HTTP response."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class TenantResolutionError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "tenant_unresolved"


class MailDeliveryError(AppError):
    """The mail server refused or could not be reached.

    502 rather than 500: the request was valid and we did our part — an upstream we
    depend on failed. It also tells the caller retrying is reasonable, which for a
    rejected recipient or a momentary Gmail hiccup it is.
    """

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "mail_delivery_failed"


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _safe_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """Reduce Pydantic's error list to what is safe and useful to return.

    Two things are dropped from each entry:

    `input` — Pydantic echoes the offending value back. On a failed login that is
    the submitted password, reflected verbatim into a response body that will end
    up in browser consoles, proxy logs and error trackers.

    `ctx` — carries the original exception *object*, which is not JSON serialisable,
    and otherwise exposes validator internals that mean nothing to a caller.
    """
    return [
        {"type": err.get("type"), "loc": list(err.get("loc", [])), "msg": err.get("msg")}
        for err in exc.errors()
    ]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = (
            {"WWW-Authenticate": "Bearer"}
            if exc.status_code == status.HTTP_401_UNAUTHORIZED
            else None
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Literal 422 rather than a status constant: Starlette renamed
        # HTTP_422_UNPROCESSABLE_ENTITY to ..._CONTENT, and the old name now warns.
        # The number is the stable thing.
        return JSONResponse(
            status_code=422,
            content=_envelope(
                "validation_error", "Request validation failed", {"errors": _safe_errors(exc)}
            ),
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        # Constraint names are deliberately stable (see db/base.py naming convention),
        # so mapping a violation back to a useful message is possible without parsing
        # driver text. The raw DB message is never echoed: it can contain another
        # tenant's column values from the conflicting row.
        constraint = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_envelope(
                "conflict",
                "The request conflicts with existing data.",
                {"constraint": constraint} if constraint else {},
            ),
        )
