"""Orchestrator for multi-source company enrichment."""

from __future__ import annotations

import logging
import time
from typing import Any

from biradar.sources.enrichment import (
    bundesanzeiger,  # noqa: F401
    github,  # noqa: F401
    handelsregister,  # noqa: F401
    north_data,  # noqa: F401
    website,  # noqa: F401
    wikidata,  # noqa: F401
)
from biradar.sources.enrichment.models import (
    EnrichmentResult,
    EnrichmentSourceDefinition,
)
from biradar.sources.enrichment.registry import (
    get_registered_enrichment_sources,
    is_source_disabled,
)
from biradar.sources.enrichment.runtime import _get_enrichment_config

logger = logging.getLogger(__name__)


def _is_source_enabled(source_name: str, enrichment_config: Any) -> bool:
    """Resolve whether a registered source is enabled in config."""
    source_flags = getattr(enrichment_config, "sources", {}) or {}
    return bool(source_flags.get(source_name, True))


def _resolve_enrichment_sources() -> list[EnrichmentSourceDefinition]:
    """Resolve registered sources after applying config-based enablement."""
    enrichment_config = _get_enrichment_config()
    return [
        source
        for source in get_registered_enrichment_sources()
        if _is_source_enabled(source.name, enrichment_config)
    ]


def _aggregate_result(sources_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate flat fields from source results for DB persistence."""
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

    for src in sources_results:
        src_name = src.get("source", "")

        if src_name == "handelsregister":
            lf = src.get("legal_form")
            if lf:
                legal_form = lf
                sector = f"Legal form: {lf}"
            registry_court = src.get("registry_court") or registry_court
            registry_number = src.get("registry_number") or registry_number
            company_status = src.get("status") or company_status

        if src_name == "website":
            website_url = src.get("url")
            website_status = src.get("status_code")
            ts = src.get("tech_signals")
            if ts:
                tech_stack = ", ".join(ts)

        if src_name == "wikidata":
            website_url = src.get("website_url") or website_url
            sector = src.get("sector") or sector

        if src_name == "github":
            github_org = src.get("org_name")
            ts = src.get("language")
            if ts and not tech_stack:
                tech_stack = ", ".join(ts) if isinstance(ts, list) else str(ts)

        if src_name == "bundesanzeiger":
            rev = src.get("revenue_estimate")
            if rev:
                funding_info = f"Revenue: {rev}"
            reports = src.get("annual_reports")
            if reports and not funding_info:
                funding_info = f"Reports: {', '.join(reports)}"

        if src_name == "north_data":
            sector = src.get("sector") or sector
            registry_number = src.get("registry_number") or registry_number

    return {
        "sector": sector,
        "tech_stack": tech_stack,
        "website_url": website_url,
        "website_status": website_status,
        "github_org": github_org,
        "funding_info": funding_info,
        "legal_form": legal_form,
        "registry_court": registry_court,
        "registry_number": registry_number,
        "company_status": company_status,
    }


def enrich_candidate(company_name: str) -> EnrichmentResult:
    """Run enrichment from all free sources for a candidate company."""
    if not company_name:
        return EnrichmentResult(
            company_name=company_name or "",
            errors=["Missing company_name"],
            enriched=False,
        )

    enrichment_config = _get_enrichment_config()
    if not enrichment_config.enabled:
        return EnrichmentResult(
            company_name=company_name,
            errors=["Enrichment is disabled in config/sources.yaml"],
            enriched=False,
        )

    errors: list[str] = []
    sources_results: list[dict[str, Any]] = []

    source_defs = _resolve_enrichment_sources()
    if not source_defs:
        return EnrichmentResult(
            company_name=company_name,
            errors=["No enrichment sources are enabled"],
            enriched=False,
        )

    for idx, source in enumerate(source_defs):
        source_name = source.name
        if is_source_disabled(source_name):
            errors.append(f"{source_name}: skipped (disabled after terminal error)")
            continue

        if idx > 0:
            time.sleep(enrichment_config.delay_between_sources)

        try:
            logger.debug("Enriching '%s' via %s ...", company_name, source_name)
            result = source.lookup_fn(company_name)
            if result is not None:
                sources_results.append(result)
            else:
                errors.append(f"{source_name}: no data returned")
        except Exception as exc:
            msg = f"{source_name}: unexpected error: {exc}"
            logger.warning(
                "Enrichment error for '%s' via %s: %s",
                company_name,
                source_name,
                exc,
            )
            errors.append(msg)

    aggregated = _aggregate_result(sources_results)

    logger.info(
        "Enrichment complete for '%s': %d sources, %d errors",
        company_name,
        len(sources_results),
        len(errors),
    )

    return EnrichmentResult(
        company_name=company_name,
        sources=sources_results,
        errors=errors,
        enriched=bool(sources_results),
        **aggregated,
    )
