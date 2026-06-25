"""Safe FastAPI request-validation error helpers."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


SAFE_MESSAGE_BY_TYPE = {
    "extra_forbidden": "Extra fields are not permitted.",
    "greater_than": "Value is out of range.",
    "greater_than_equal": "Value is out of range.",
    "less_than": "Value is out of range.",
    "less_than_equal": "Value is out of range.",
    "list_type": "Value must be a list.",
    "missing": "Field is required.",
    "string_too_long": "Value is too long.",
    "string_too_short": "Value is too short.",
}


def safe_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, object]]:
    safe_errors: list[dict[str, object]] = []

    for error in errors:
        loc = error.get("loc")
        error_type = str(error.get("type", ""))
        safe_errors.append(
            {
                "loc": list(loc) if isinstance(loc, (list, tuple)) else [],
                "msg": SAFE_MESSAGE_BY_TYPE.get(error_type, "Invalid value."),
            }
        )

    return safe_errors


async def safe_request_validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": safe_validation_errors(exc.errors())},
    )
