"""Models and source definitions for enrichment."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


class EnrichmentResult(BaseModel):
    """Aggregated result from all enrichment sources."""

    company_name: str
    sources: list[dict[str, Any]] = []
    errors: list[str] = []
    enriched: bool = False
    sector: str | None = None
    tech_stack: str | None = None
    website_url: str | None = None
    website_status: int | None = None
    github_org: str | None = None
    funding_info: str | None = None
    legal_form: str | None = None
    registry_court: str | None = None
    registry_number: str | None = None
    company_status: str | None = None


EnrichmentLookupFn = Callable[[str], dict[str, Any] | None]


@dataclass(frozen=True)
class EnrichmentSourceDefinition:
    """Registered enrichment source metadata."""

    name: str
    lookup_fn: EnrichmentLookupFn
