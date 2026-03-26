"""Structured tool response helpers."""

from __future__ import annotations

from typing import Any


def ok(details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "error_code": None, "message": "", "details": details or {}}


def fail(error_code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": False, "error_code": error_code, "message": message, "details": details or {}}
