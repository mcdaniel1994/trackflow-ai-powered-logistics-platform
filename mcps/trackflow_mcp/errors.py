"""Stable, machine-readable MCP tool failure contracts."""

from __future__ import annotations

import json
from enum import StrEnum

from fastmcp.exceptions import ToolError


class ErrorCode(StrEnum):
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
    INVALID_INPUT = "INVALID_INPUT"
    NOT_FOUND = "NOT_FOUND"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    INVENTORY_READ_ONLY = "INVENTORY_READ_ONLY"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"


class ToolFailure(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_tool_error(self) -> ToolError:
        return ToolError(json.dumps({"error": self.code, "message": self.message}))
