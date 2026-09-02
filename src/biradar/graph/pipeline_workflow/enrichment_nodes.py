"""Enrichment node: external source lookups for non-quarantined candidates."""

# pyright: reportArgumentType=false, reportReturnType=false
#
# Scoped to this module. Two upstream limitations, neither first-party:
#   * `{**state, ...}` over a TypedDict widens to a plain dict, so every node
#     return is reported as not assignable to PipelineWorkflowState.
#   * StateGraph.add_node passes an unbound NodeInputT that does not resolve to
#     the concrete state type.
# Keep these off only here; the rules stay enabled everywhere else.

import logging
from typing import Any

from biradar.graph.pipeline_workflow.claims import _build_enrichment_claims
from biradar.graph.pipeline_workflow.node_helpers import _active_candidates
from biradar.graph.pipeline_workflow.types import EnricherFn
from biradar.graph.state import PipelineWorkflowState
from biradar.sources.enrichment import enrich_candidate

logger = logging.getLogger(__name__)


def enrichment_node(
    state: PipelineWorkflowState,
    enricher: EnricherFn = enrich_candidate,
) -> PipelineWorkflowState:
    """Enrichment for candidates that passed scoring. Low-score candidates skip this."""
    logger.info("Executing enrichment node")
    enrichment_results = dict(state.get("enrichment_results", {}))

    for candidate in _active_candidates(state["candidates"]):
        candidate_id = candidate.get("candidate_id", "unknown")
        if candidate_id in enrichment_results:
            continue  # already enriched on previous pass

        company_name = candidate.get("company_name", "")
        if not company_name:
            enrichment_results[candidate_id] = _skipped_enrichment_payload()
            continue

        result = enricher(company_name)
        enrichment_results[candidate_id] = _enrichment_payload(result)

    return {
        **state,
        "enrichment_results": enrichment_results,
        "current_step": "risk_review",
    }


def _skipped_enrichment_payload() -> dict[str, Any]:
    """Payload recorded when a candidate has no company name to enrich."""
    return {
        "enriched": False,
        "status": "skipped",
        "claims": [],
        "note": "No company name available for enrichment",
        "data": {},
        "errors": [],
    }


def _enrichment_payload(result: Any) -> dict[str, Any]:
    """Shape an enrichment result into the state's per-candidate payload."""
    return {
        "enriched": result.enriched,
        "status": "success" if result.enriched else "unavailable",
        "claims": _build_enrichment_claims(result),
        "data": {
            "sector": result.sector,
            "tech_stack": result.tech_stack,
            "website_url": result.website_url,
            "website_status": result.website_status,
            "github_org": result.github_org,
            "funding_info": result.funding_info,
            "legal_form": result.legal_form,
            "registry_court": result.registry_court,
            "registry_number": result.registry_number,
            "company_status": result.company_status,
        },
        "errors": result.errors,
    }
