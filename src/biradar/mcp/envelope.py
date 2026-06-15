"""Unified result envelope for MCP tools and services."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResultEnvelope(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    audit_id: str | None = None
    next_action: str | None = None
