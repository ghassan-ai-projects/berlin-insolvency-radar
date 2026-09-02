"""Extraction node: structured LLM extraction of filing facts."""

# pyright: reportArgumentType=false, reportReturnType=false
#
# Scoped to this module. Two upstream limitations, neither first-party:
#   * `{**state, ...}` over a TypedDict widens to a plain dict, so every node
#     return is reported as not assignable to PipelineWorkflowState.
#   * StateGraph.add_node passes an unbound NodeInputT that does not resolve to
#     the concrete state type.
# Keep these off only here; the rules stay enabled everywhere else.

import logging
import uuid

from biradar.agents.extraction import extract_filing_facts
from biradar.graph.pipeline_workflow.node_helpers import (
    _active_candidates,
    _copied_errors,
    _quarantine,
)
from biradar.graph.pipeline_workflow.types import ExtractorFn
from biradar.graph.state import ExtractionPayload, PipelineWorkflowState

logger = logging.getLogger(__name__)


def extraction_node(
    state: PipelineWorkflowState,
    extractor: ExtractorFn = extract_filing_facts,
) -> PipelineWorkflowState:
    """Structured extraction of filing facts."""
    logger.info("Executing extraction node")
    extraction_results: dict[str, ExtractionPayload] = dict(
        state.get("extraction_results", {})
    )
    errors = _copied_errors(state)

    for candidate in _active_candidates(state.get("candidates", [])):
        candidate_id = candidate.get("candidate_id", str(uuid.uuid4()))
        if candidate_id in extraction_results:
            continue  # already extracted on previous pass

        try:
            result = extractor(
                candidate.get("raw_text", ""),
                candidate.get("source_url", ""),
            )
            extraction_results[candidate_id] = result.model_dump()
            if result.is_consumer_likely:
                _quarantine(candidate, "extraction_flagged_consumer")
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", candidate_id, exc)
            _quarantine(candidate, "extraction_failed")
            errors.append(f"Extraction failed for {candidate_id}: {exc}")

    return {
        **state,
        "extraction_results": extraction_results,
        "errors": errors,
        "current_step": "enrichment",
    }
