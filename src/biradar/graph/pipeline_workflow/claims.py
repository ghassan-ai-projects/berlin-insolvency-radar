"""Shaping of enrichment results into source-normalized claim rows."""

from typing import Any

from biradar.graph.state import EnrichmentClaimPayload

_ENRICHED_CLAIM_FIELDS = (
    "sector",
    "legal_form",
    "registry_court",
    "registry_number",
    "company_status",
    "tech_stack",
    "github_org",
    "funding_info",
    "euid",
    "last_update",
)


def _build_enrichment_claims(result: Any) -> list[EnrichmentClaimPayload]:
    """Build claim rows from an enrichment result."""
    claims: list[EnrichmentClaimPayload] = []
    for src in result.sources:
        source_name = src.get("source", "unknown")
        source_url = src.get("url") or src.get("source_url") or None
        for field in _ENRICHED_CLAIM_FIELDS:
            val = src.get(field)
            if val:
                claims.append(
                    {
                        "field": field,
                        "value": str(val),
                        "classification": "verified",
                        "source_provider": source_name,
                        "source_url": source_url,
                        "note": f"From {source_name}",
                    }
                )
    return claims
