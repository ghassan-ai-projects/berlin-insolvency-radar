"""Workflow builder: registers the pipeline nodes and wires their edges."""

# pyright: reportArgumentType=false, reportReturnType=false
#
# Scoped to this module. Two upstream limitations, neither first-party:
#   * `{**state, ...}` over a TypedDict widens to a plain dict, so every node
#     return is reported as not assignable to PipelineWorkflowState.
#   * StateGraph.add_node passes an unbound NodeInputT that does not resolve to
#     the concrete state type.
# Keep these off only here; the rules stay enabled everywhere else.

from typing import Literal

from langgraph.graph import END, START, StateGraph

from biradar.agents.extraction import extract_filing_facts
from biradar.agents.risk_review import review_candidate_risk
from biradar.graph.pipeline_workflow.enrichment_nodes import enrichment_node
from biradar.graph.pipeline_workflow.extraction_nodes import extraction_node
from biradar.graph.pipeline_workflow.intake_nodes import (
    dedupe_node,
    ingest_node,
    normalize_and_compliance_node,
)
from biradar.graph.pipeline_workflow.output_nodes import (
    draft_assembly_node,
    export_node,
)
from biradar.graph.pipeline_workflow.risk_review_nodes import risk_review_node
from biradar.graph.pipeline_workflow.scoring_nodes import scoring_node
from biradar.graph.pipeline_workflow.types import (
    EnricherFn,
    ExtractorFn,
    RiskReviewerFn,
)
from biradar.graph.state import PipelineWorkflowState
from biradar.sources.enrichment import enrich_candidate


def build_pipeline_workflow(
    extractor: ExtractorFn | None = None,
    risk_reviewer: RiskReviewerFn | None = None,
    enricher: EnricherFn | None = None,
) -> StateGraph:
    """Build the LangGraph pipeline."""
    resolved_extractor = extractor or extract_filing_facts
    resolved_risk_reviewer = risk_reviewer or review_candidate_risk
    resolved_enricher = enricher or enrich_candidate
    workflow = StateGraph(PipelineWorkflowState)

    _register_pipeline_nodes(
        workflow, resolved_extractor, resolved_risk_reviewer, resolved_enricher
    )
    _wire_pipeline_edges(workflow)
    return workflow


def _register_pipeline_nodes(
    workflow: StateGraph,
    extractor: ExtractorFn,
    risk_reviewer: RiskReviewerFn,
    enricher: EnricherFn,
) -> None:
    """Register every pipeline node, binding the injected actors via lambdas."""
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("normalize_and_compliance", normalize_and_compliance_node)
    workflow.add_node("dedupe", dedupe_node)
    workflow.add_node("extraction", lambda state: extraction_node(state, extractor))
    workflow.add_node("enrichment", lambda state: enrichment_node(state, enricher))
    workflow.add_node("scoring", scoring_node)
    workflow.add_node(
        "risk_review", lambda state: risk_review_node(state, risk_reviewer)
    )
    workflow.add_node("draft_assembly", draft_assembly_node)
    workflow.add_node("export", export_node)


def _wire_pipeline_edges(workflow: StateGraph) -> None:
    """Wire the linear flow plus the risk-review retry loop."""
    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "normalize_and_compliance")
    workflow.add_edge("normalize_and_compliance", "dedupe")
    workflow.add_edge("dedupe", "extraction")
    workflow.add_edge("extraction", "scoring")
    workflow.add_edge("scoring", "enrichment")
    workflow.add_edge("enrichment", "risk_review")
    workflow.add_conditional_edges(
        "risk_review",
        _route_after_risk_review,
        {"extraction": "extraction", "draft_assembly": "draft_assembly"},
    )
    workflow.add_edge("draft_assembly", "export")
    workflow.add_edge("export", END)


def _route_after_risk_review(
    state: PipelineWorkflowState,
) -> Literal["extraction", "draft_assembly"]:
    return (
        "extraction" if state.get("current_step") == "extraction" else "draft_assembly"
    )
