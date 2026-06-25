from __future__ import annotations

import asyncio
import json

from fastapi import Request
from fastapi.exceptions import RequestValidationError

from trackflow_auth import safe_request_validation_exception_handler, safe_validation_errors


def request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


def test_safe_validation_errors_strip_input_ctx_and_exception_messages():
    secret_password = "pw"
    secret_email = "private@example.com"
    errors = [
        {
            "type": "string_too_short",
            "loc": ("body", "new_password"),
            "msg": "String should have at least 8 characters",
            "input": secret_password,
            "ctx": {"min_length": 8},
        },
        {
            "type": "value_error",
            "loc": ("body", "email"),
            "msg": f"Value error, {secret_email} is invalid",
            "input": secret_email,
        },
    ]

    safe = safe_validation_errors(errors)

    assert safe == [
        {"loc": ["body", "new_password"], "msg": "Value is too short."},
        {"loc": ["body", "email"], "msg": "Invalid value."},
    ]
    serialized = json.dumps(safe)
    assert "input" not in serialized
    assert "ctx" not in serialized
    assert secret_password not in serialized
    assert secret_email not in serialized


def test_safe_request_validation_handler_returns_only_loc_and_msg():
    secret_token = "reset-token-secret"
    exc = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "token"),
                "msg": "Field required",
                "input": {"token": secret_token},
            }
        ]
    )

    response = asyncio.run(safe_request_validation_exception_handler(request(), exc))
    body = json.loads(response.body)

    assert response.status_code == 422
    assert body == {"detail": [{"loc": ["body", "token"], "msg": "Field is required."}]}
    assert secret_token not in response.body.decode("utf-8")
