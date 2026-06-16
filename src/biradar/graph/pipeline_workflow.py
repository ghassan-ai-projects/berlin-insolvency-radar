"""Agentic LangGraph workflow for the production pipeline."""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from biradar.agents.extraction import extract_filing_facts
from biradar.agents.risk_review import review_candidate_risk
from biradar.config.settings import get_settings, load_config
from biradar.domain.compliance import evaluate_compliance
from biradar.domain.dedupe import deduplicate_candidates
from biradar.domain.scoring import ScoreInput, compute_score
from biradar.graph.state import PipelineWorkflowState
from biradar.output.export import generate_json_package, generate_markdown_draft
from biradar.sources.enrichment import enrich_candidate

logger = logging.getLogger(__name__)

ExtractorFn = Callable[[str, str], Any]
RiskReviewerFn = Callable[[dict[str, Any], dict[str, Any], dict[str, Any], str], Any]
EnricherFn = Callable[[str], Any]


def _build_enrichment_claims(result: Any) -> list[dict[str, Any]]:
    """Build claim rows from an enrichment result."""
    claims: list[dict[str, Any]] = []
    for src in result.sources:
        source_name = src.get("source", "unknown")
        source_url = src.get("url") or None
        for field in (
            "sector",
            "legal_form",
            "registry_court",
            "registry_number",
            "company_status",
            "tech_stack",
            "github_org",
            "funding_info",
        ):
            val = src.get(field)
            if val:
                claims.append(
                    {
                        "field": field,
                        "value": str(val),
                        "classification": "verified",
                        "source_url": source_url,
                        "note": f"From {source_name}",
                    }
                )
    return claims


def _build_score_input(
    candidate: dict[str, Any],
    extraction_data: dict[str, Any],
    enrichment_data: dict[str, Any],
) -> ScoreInput:
    """Build deterministic score dimensions from available evidence."""
    legal_form = (
        candidate.get("legal_form") or extraction_data.get("legal_form") or ""
    ).upper()
    stage = (
        candidate.get("proceeding_stage")
        or extraction_data.get("proceeding_stage")
        or ""
    ).lower()
    enrichment_payload = enrichment_data.get("data", {})
    has_registry = bool(enrichment_payload.get("registry_number"))
    has_website = bool(enrichment_payload.get("website_url"))
    has_github = bool(enrichment_payload.get("github_org"))
    has_funding = bool(enrichment_payload.get("funding_info"))
    evidence_count = len(extraction_data.get("evidence_snippets", {}))

    company_value = 2
    if legal_form in {"GMBH", "AG", "SE", "GMBH & CO. KG"}:
        company_value += 1
    if has_registry:
        company_value += 1
    if has_funding:
        company_value += 1

    asset_quality = 2 + int(has_website) + int(has_github)
    sector_attractiveness = (
        2 + int(has_github) + int(bool(enrichment_payload.get("tech_stack")))
    )
    speed_of_action = 2 + int("er" in stage) + int(evidence_count >= 2)
    legal_risk = 3 - int(has_registry) - int(evidence_count >= 2)

    def clamp(value: int) -> int:
        return max(1, min(5, value))

    return ScoreInput(
        company_value=clamp(company_value),
        asset_quality=clamp(asset_quality),
        sector_attractiveness=clamp(sector_attractiveness),
        speed_of_action=clamp(speed_of_action),
        legal_risk=clamp(legal_risk),
        rationale={
            "method": "deterministic_heuristics",
            "evidence_count": str(evidence_count),
            "has_registry": str(has_registry),
            "has_website": str(has_website),
            "has_github": str(has_github),
            "has_funding": str(has_funding),
        },
    )


def ingest_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Initial node: seed the state from already-fetched raw records."""
    logger.info("Executing ingest node")
    return {**state, "current_step": "normalize"}


def normalize_and_compliance_node(
    state: PipelineWorkflowState,
) -> PipelineWorkflowState:
    """Normalize records and apply deterministic corporate-only filtering."""
    logger.info("Executing normalize and compliance node")
    valid_candidates = []

    for record in state["raw_records"]:
        is_allowed, reason = evaluate_compliance(
            legal_form=record.get("legal_form"),
            raw_text=record.get("raw_text", ""),
            company_name=record.get("company_name"),
        )
        status = "deduped_candidate" if is_allowed else "quarantined"
        valid_candidates.append(
            {
                **record,
                "status": status,
                "compliance_reason": None if is_allowed else reason,
            }
        )

    return {**state, "candidates": valid_candidates, "current_step": "dedupe"}


def dedupe_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Deterministic deduplication."""
    logger.info("Executing dedupe node")
    deduped = deduplicate_candidates(state["candidates"])
    return {**state, "candidates": deduped, "current_step": "extraction"}


def extraction_node(
    state: PipelineWorkflowState,
    extractor: ExtractorFn = extract_filing_facts,
) -> PipelineWorkflowState:
    """Structured extraction of filing facts."""
    logger.info("Executing extraction node")
    extraction_results: dict[str, dict[str, Any]] = {}
    errors = list(state.get("errors", []))

    for candidate in state.get("candidates", []):
        if candidate.get("status") == "quarantined":
            continue

        candidate_id = candidate.get("candidate_id", str(uuid.uuid4()))
        try:
            result = extractor(
                candidate.get("raw_text", ""),
                candidate.get("source_url", ""),
            )
            extraction_results[candidate_id] = result.model_dump()
            if result.is_consumer_likely:
                candidate["status"] = "quarantined"
                candidate["quarantine_reason"] = "extraction_flagged_consumer"
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", candidate_id, exc)
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "extraction_failed"
            errors.append(f"Extraction failed for {candidate_id}: {exc}")

    return {
        **state,
        "extraction_results": extraction_results,
        "errors": errors,
        "current_step": "enrichment",
    }


def enrichment_node(
    state: PipelineWorkflowState,
    enricher: EnricherFn = enrich_candidate,
) -> PipelineWorkflowState:
    """Enrichment using free/public sources."""
    logger.info("Executing enrichment node")
    enrichment_results: dict[str, dict[str, Any]] = {}

    for candidate in state["candidates"]:
        if candidate["status"] == "quarantined":
            continue

        candidate_id = candidate.get("candidate_id", "unknown")
        if candidate.get("enrichment_http_status") == 403 or candidate.get(
            "enrichment_blocked"
        ):
            enrichment_results[candidate_id] = {
                "enriched": False,
                "status": "blocked_by_anti_bot",
                "claims": [],
                "blocked_source": candidate.get("enrichment_source", "public_source"),
                "data": {},
                "errors": [],
            }
            continue

        company_name = candidate.get("company_name", "")
        if not company_name:
            enrichment_results[candidate_id] = {
                "enriched": False,
                "status": "skipped",
                "claims": [],
                "note": "No company name available for enrichment",
                "data": {},
                "errors": [],
            }
            continue

        result = enricher(company_name)
        enrichment_results[candidate_id] = {
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

    return {
        **state,
        "enrichment_results": enrichment_results,
        "current_step": "scoring",
    }


def scoring_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Deterministic scoring from extracted and enriched evidence."""
    logger.info("Executing scoring node")
    settings = get_settings()
    config = load_config(settings.project_root / "config")
    scores: dict[str, dict[str, Any]] = {}

    for candidate in state["candidates"]:
        if candidate["status"] == "quarantined":
            continue

        candidate_id = candidate.get("candidate_id", "unknown")
        extraction_data = state.get("extraction_results", {}).get(candidate_id, {})
        enrichment_data = state.get("enrichment_results", {}).get(candidate_id, {})

        try:
            proposed_scores = _build_score_input(
                candidate, extraction_data, enrichment_data
            )
            result = compute_score(
                proposed_scores, config.scoring.weights, config.scoring.thresholds
            )
            score_payload = {
                "company_value": proposed_scores.company_value,
                "asset_quality": proposed_scores.asset_quality,
                "sector_attractiveness": proposed_scores.sector_attractiveness,
                "speed_of_action": proposed_scores.speed_of_action,
                "legal_risk": proposed_scores.legal_risk,
                "computed_score": result.computed_score,
                "category": result.category,
                "status": "approved",
                "rationale": proposed_scores.rationale,
            }
            scores[candidate_id] = score_payload
            candidate["score"] = score_payload

            threshold = config.scoring.thresholds.get("interesting", 2.0)
            if result.computed_score < threshold:
                candidate["status"] = "quarantined"
                candidate["quarantine_reason"] = "low_score"
        except Exception as exc:
            logger.error("Scoring failed for %s: %s", candidate_id, exc)
            scores[candidate_id] = {"status": "failed", "error": str(exc)}
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "scoring_failed"

    return {**state, "scores": scores, "current_step": "risk_review"}


def risk_review_node(
    state: PipelineWorkflowState,
    risk_reviewer: RiskReviewerFn = review_candidate_risk,
) -> PipelineWorkflowState:
    """Risk review with limited retry before quarantine."""
    logger.info("Executing risk review node")

    retry_counts = dict(state.get("retry_counts", {}))
    risk_reviews = dict(state.get("risk_reviews", {}))
    warnings = list(state.get("warnings", []))
    errors = list(state.get("errors", []))
    needs_retry = False

    for candidate in state.get("candidates", []):
        if candidate.get("status") == "quarantined":
            continue

        candidate_id = candidate.get("candidate_id", "unknown")
        retries = retry_counts.get(candidate_id, 0)
        draft_thesis = (
            f"Opportunity in {candidate.get('proceeding_stage', 'insolvency')} "
            f"for {candidate.get('company_name', 'Unknown')}."
        )
        extraction_data = state.get("extraction_results", {}).get(candidate_id, {})
        enrichment_data = state.get("enrichment_results", {}).get(candidate_id, {})
        evidence_snippets = extraction_data.get("evidence_snippets", {})
        unsupported_claims = [
            claim
            for claim in enrichment_data.get("claims", [])
            if claim.get("classification") != "inference"
            and not claim.get("source_url")
        ]

        if unsupported_claims:
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "unsupported_enrichment_claims"
            risk_reviews[candidate_id] = {
                "status": "quarantined",
                "retries": retries,
                "reasons": ["unsupported_enrichment_claims"],
                "unsupported_claims": unsupported_claims,
            }
            warnings.append(
                f"Quarantined {candidate_id}: unsupported enrichment claims."
            )
            continue

        if not evidence_snippets:
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "missing_extraction_evidence"
            risk_reviews[candidate_id] = {
                "status": "quarantined",
                "retries": retries,
                "reasons": ["missing_extraction_evidence"],
                "unsupported_claims": [],
            }
            warnings.append(f"Quarantined {candidate_id}: missing extraction evidence.")
            continue

        try:
            result = risk_reviewer(
                candidate, extraction_data, enrichment_data, draft_thesis
            )
            if not result.passed_review:
                if retries < 2:
                    retry_counts[candidate_id] = retries + 1
                    needs_retry = True
                else:
                    candidate["status"] = "quarantined"
                    candidate["quarantine_reason"] = "risk_review_failed_max_retries"
                    risk_reviews[candidate_id] = {
                        "status": "quarantined",
                        "retries": retries,
                        "reasons": result.rejection_reasons or ["review_rejected"],
                    }
            else:
                candidate["status"] = "publish_ready"
                risk_reviews[candidate_id] = {
                    "status": "passed",
                    "retries": retries,
                    "confidence": result.confidence_in_review,
                    "unsupported_claims": [],
                }
        except Exception as exc:
            logger.error("Risk review failed for %s: %s", candidate_id, exc)
            errors.append(f"Risk review failed for {candidate_id}: {exc}")
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "risk_review_system_error"

    current_step: Literal["extraction", "draft_assembly"]
    current_step = "extraction" if needs_retry else "draft_assembly"
    return {
        **state,
        "retry_counts": retry_counts,
        "risk_reviews": risk_reviews,
        "warnings": warnings,
        "errors": errors,
        "current_step": current_step,
    }


def draft_assembly_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Assemble export-ready Markdown and JSON."""
    logger.info("Executing draft assembly node")
    warnings = list(state.get("warnings", []))
    export_ready_candidates = []

    for candidate in state["candidates"]:
        if candidate.get("status") != "publish_ready":
            continue

        candidate_id = candidate["candidate_id"]
        score_payload = state.get("scores", {}).get(candidate_id)
        extraction_payload = state.get("extraction_results", {}).get(candidate_id, {})
        evidence_snippets = extraction_payload.get("evidence_snippets", {})
        if not score_payload or score_payload.get("status") != "approved":
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "missing_approved_score"
            warnings.append(
                f"Excluded {candidate_id} from export: missing approved score."
            )
            continue
        if not evidence_snippets:
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "missing_evidence"
            warnings.append(f"Excluded {candidate_id} from export: missing evidence.")
            continue

        enrichment_claims = (
            state.get("enrichment_results", {}).get(candidate_id, {}).get("claims", [])
        )
        factual_fields: dict[str, Any] = {}
        for field in (
            "company_name",
            "case_number",
            "publication_date",
            "proceeding_stage",
        ):
            value = extraction_payload.get(field)
            if value is None:
                value = candidate.get(field)
            if value is not None:
                factual_fields[field] = value

        candidate["export_confidence"] = (
            state.get("risk_reviews", {}).get(candidate_id, {}).get("confidence")
        )
        candidate["evidence_summary"] = evidence_snippets
        candidate["enrichment_claims"] = enrichment_claims
        candidate["unsupported_claims"] = (
            state.get("risk_reviews", {})
            .get(candidate_id, {})
            .get("unsupported_claims", [])
        )
        candidate["content_sections"] = {
            "facts": factual_fields,
            "inferences": enrichment_claims,
            "editorial": {
                "score": score_payload,
                "thesis": (
                    "Ranked from deterministic score for "
                    f"{candidate.get('company_name', 'Unknown Company')}."
                ),
            },
        }
        export_ready_candidates.append(candidate)

    total_candidates = len(state["candidates"])
    quarantined_candidates = len(
        [
            candidate
            for candidate in state["candidates"]
            if candidate.get("status") == "quarantined"
        ]
    )
    issue_draft = {
        "title": "Weekly Berlin Insolvency Radar",
        "source_run_id": state.get("source_run_id"),
        "generated_at": datetime.now(UTC).isoformat(),
        "warnings": warnings,
        "audit_summary": {
            "source_run_id": state.get("source_run_id"),
            "total_raw_records": len(state.get("raw_records", [])),
            "total_candidates": total_candidates,
            "publish_ready_candidates": len(export_ready_candidates),
            "quarantined_candidates": quarantined_candidates,
            "error_count": len(state.get("errors", [])),
            "warning_count": len(warnings),
            "current_step": "draft_assembly",
        },
        "candidates": export_ready_candidates,
    }
    return {
        **state,
        "issue_draft": issue_draft,
        "warnings": warnings,
        "current_step": "export",
    }


def export_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Final export gate and persistence."""
    logger.info("Executing export node")
    settings = get_settings()
    export_dir = settings.data_dir / "exports"
    issue_data = state.get("issue_draft", {})
    markdown_path = generate_markdown_draft(issue_data, export_dir)
    json_path = generate_json_package(issue_data, export_dir)
    return {
        **state,
        "export_path": markdown_path,
        "warnings": state.get("warnings", [])
        + [f"Exported to {markdown_path} and {json_path}"],
        "current_step": "completed",
    }


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

    workflow.add_node("ingest", ingest_node)
    workflow.add_node("normalize_and_compliance", normalize_and_compliance_node)
    workflow.add_node("dedupe", dedupe_node)
    workflow.add_node(
        "extraction", lambda state: extraction_node(state, resolved_extractor)
    )
    workflow.add_node(
        "enrichment", lambda state: enrichment_node(state, resolved_enricher)
    )
    workflow.add_node("scoring", scoring_node)
    workflow.add_node(
        "risk_review",
        lambda state: risk_review_node(state, resolved_risk_reviewer),
    )
    workflow.add_node("draft_assembly", draft_assembly_node)
    workflow.add_node("export", export_node)

    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "normalize_and_compliance")
    workflow.add_edge("normalize_and_compliance", "dedupe")
    workflow.add_edge("dedupe", "extraction")
    workflow.add_edge("extraction", "enrichment")
    workflow.add_edge("enrichment", "scoring")
    workflow.add_edge("scoring", "risk_review")

    def review_router(
        state: PipelineWorkflowState,
    ) -> Literal["extraction", "draft_assembly"]:
        return (
            "extraction"
            if state.get("current_step") == "extraction"
            else "draft_assembly"
        )

    workflow.add_conditional_edges(
        "risk_review",
        review_router,
        {"extraction": "extraction", "draft_assembly": "draft_assembly"},
    )
    workflow.add_edge("draft_assembly", "export")
    workflow.add_edge("export", END)
    return workflow
