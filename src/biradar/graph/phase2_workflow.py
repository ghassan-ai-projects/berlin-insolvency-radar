"""Phase 2 fully agentic LangGraph workflow."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from langgraph.graph import END, START, StateGraph

from biradar.agents.extraction import extract_filing_facts
from biradar.agents.risk_review import review_candidate_risk
from biradar.config.settings import get_settings, load_config
from biradar.domain.compliance import evaluate_compliance
from biradar.domain.dedupe import deduplicate_candidates
from biradar.domain.scoring import ScoreInput, compute_score
from biradar.graph.state import Phase2WorkflowState
from biradar.output.export import generate_json_package, generate_markdown_draft
from biradar.sources.enrichment import enrich_candidate

logger = logging.getLogger(__name__)


def _build_enrichment_claims(result) -> list[dict]:
    """Build claims list from an EnrichmentResult for the enrichment_results state."""
    claims: list[dict] = []
    for src in result.sources:
        source_name = src.get("source", "unknown")
        source_url = src.get("url") or None
        for field in ("sector", "legal_form", "registry_court", "registry_number",
                      "company_status", "tech_stack", "github_org", "funding_info"):
            val = src.get(field)
            if val and val != "Unknown":
                claims.append({
                    "field": field,
                    "value": str(val),
                    "classification": "verified",
                    "source_url": source_url,
                    "note": f"From {source_name}",
                })
    if not claims and result.sector:
        claims.append({
            "field": "sector",
            "value": "Unknown",
            "classification": "inference",
            "source_url": None,
            "note": "No verified free/public enrichment source returned "
                    "a stronger claim in local mode.",
        })
    return claims


def ingest_node(state: Phase2WorkflowState) -> Phase2WorkflowState:
    """Initial node: fetches raw records from the source."""
    logger.info("Executing ingest node")
    # In a real run, this would call the OfficialPortalAdapter
    state["current_step"] = "normalize"
    return {**state}


def normalize_and_compliance_node(state: Phase2WorkflowState) -> Phase2WorkflowState:
    """Normalize records and apply deterministic corporate-only filter."""
    logger.info("Executing normalize and compliance node")
    valid_candidates = []

    for record in state["raw_records"]:
        legal_form = record.get("legal_form")
        company_name = record.get("company_name")
        raw_text = record.get("raw_text", "")

        is_allowed, reason = evaluate_compliance(
            legal_form=legal_form,
            raw_text=raw_text,
            company_name=company_name,
        )

        if is_allowed:
            valid_candidates.append(
                {**record, "status": "deduped_candidate", "compliance_reason": None}
            )
        else:
            valid_candidates.append(
                {**record, "status": "quarantined", "compliance_reason": reason}
            )

    state["candidates"] = valid_candidates
    state["current_step"] = "dedupe"
    return {**state}


def dedupe_node(state: Phase2WorkflowState) -> Phase2WorkflowState:
    """Deterministic deduplication."""
    logger.info("Executing dedupe node")
    deduped = deduplicate_candidates(state["candidates"])
    state["candidates"] = deduped
    state["current_step"] = "extraction"
    return {**state}


def extraction_node(state: Phase2WorkflowState) -> Phase2WorkflowState:
    """LLM-based structured extraction of filing facts."""
    logger.info("Executing extraction node")
    extraction_results = {}

    for candidate in state.get("candidates", []):
        if candidate.get("status") == "quarantined":
            continue

        cid = candidate.get("candidate_id", str(uuid.uuid4()))
        raw_text = candidate.get("raw_text", "")
        source_url = candidate.get("source_url", "")

        try:
            result = extract_filing_facts(raw_text, source_url)
            extraction_results[cid] = result.model_dump()

            # If extraction flags it as likely consumer, quarantine it
            if result.is_consumer_likely:
                candidate["status"] = "quarantined"
                candidate["quarantine_reason"] = "extraction_flagged_consumer"
        except Exception as e:
            logger.error(f"Extraction failed for {cid}: {e}")
            state["errors"].append(f"Extraction failed for {cid}: {e}")

    state["extraction_results"] = extraction_results
    return {**state, "current_step": "enrichment"}


def enrichment_node(state: Phase2WorkflowState) -> Phase2WorkflowState:
    """LLM-based enrichment using free/public sources."""
    logger.info("Executing enrichment node")
    enrichment_results = {}
    for candidate in state["candidates"]:
        if candidate["status"] == "quarantined":
            continue
        cid = candidate.get("candidate_id", "unknown")

        if candidate.get("enrichment_http_status") == 403 or candidate.get(
            "enrichment_blocked"
        ):
            enrichment_results[cid] = {
                "enriched": False,
                "status": "blocked_by_anti_bot",
                "claims": [],
                "blocked_source": candidate.get("enrichment_source", "public_source"),
            }
            continue

        company_name = candidate.get("company_name", "")
        if not company_name:
            enrichment_results[cid] = {
                "enriched": False,
                "status": "skipped",
                "claims": [],
                "note": "No company name available for enrichment",
            }
            continue

        # Run enrichment (mock or real, gated by BI_RADAR_ENRICH_REAL)
        result = enrich_candidate(company_name)
        enrichment_results[cid] = {
            "enriched": result.enriched,
            "status": "success" if result.enriched else "failed",
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
    state["enrichment_results"] = enrichment_results
    state["current_step"] = "scoring"
    return {**state}


def scoring_node(state: Phase2WorkflowState) -> Phase2WorkflowState:
    """Deterministic scoring based on LLM-proposed dimensions."""
    logger.info("Executing scoring node")
    scores = {}
    settings = get_settings()
    config = load_config(settings.project_root / "config")

    for candidate in state["candidates"]:
        if candidate["status"] == "quarantined":
            continue
        cid = candidate.get("candidate_id", "unknown")

        # LLM proposes dimensions; here we simulate a valid proposal
        # In reality, this comes from the analyst/extraction agent
        proposed_scores = ScoreInput(
            company_value=3,
            asset_quality=3,
            sector_attractiveness=3,
            speed_of_action=3,
            legal_risk=2,
            rationale={"note": "Simulated proposal"},
        )

        # Deterministic validation and calculation
        try:
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
            scores[cid] = score_payload
            candidate["score"] = score_payload

            # Auto-quarantine if confidence/threshold is too low
            # Use getattr for safe access to Pydantic model attributes
            threshold = getattr(config.scoring.thresholds, "interesting", 2.0)
            if result.computed_score < threshold:
                candidate["status"] = "quarantined"
                candidate["quarantine_reason"] = "low_score"

        except Exception as e:
            logger.error(f"Scoring failed for {cid}: {e}")
            scores[cid] = {"status": "failed", "error": str(e)}

    state["scores"] = scores
    state["current_step"] = "risk_review"
    return {**state}


def risk_review_node(state: Phase2WorkflowState) -> Phase2WorkflowState:
    """Risk review with max 2 retries before auto-quarantine."""
    logger.info("Executing risk review node")

    if "retry_counts" not in state:
        state["retry_counts"] = {}

    risk_reviews = state.get("risk_reviews", {})
    needs_retry = False

    for candidate in state.get("candidates", []):
        if candidate.get("status") == "quarantined":
            continue

        cid = candidate.get("candidate_id", "unknown")
        retries = state["retry_counts"].get(cid, 0)

        # Gather context for the review
        draft_thesis = f"Opportunity in {candidate.get('proceeding_stage', 'insolvency')} for {candidate.get('company_name', 'Unknown')}."
        extraction_data = state.get("extraction_results", {}).get(cid, {})
        enrichment_data = state.get("enrichment_results", {}).get(cid, {})
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
            risk_reviews[cid] = {
                "status": "quarantined",
                "retries": retries,
                "reasons": ["unsupported_enrichment_claims"],
                "unsupported_claims": unsupported_claims,
            }
            state["warnings"].append(
                f"Quarantined {cid}: unsupported enrichment claims."
            )
            continue
        if not evidence_snippets:
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "missing_extraction_evidence"
            risk_reviews[cid] = {
                "status": "quarantined",
                "retries": retries,
                "reasons": ["missing_extraction_evidence"],
                "unsupported_claims": [],
            }
            state["warnings"].append(f"Quarantined {cid}: missing extraction evidence.")
            continue

        try:
            # Call the LLM Risk Review Agent
            result = review_candidate_risk(
                candidate, extraction_data, enrichment_data, draft_thesis
            )

            if not result.passed_review:
                if retries < 2:
                    state["retry_counts"][cid] = retries + 1
                    needs_retry = True
                    # In a full loop, we'd pass actionable_feedback_for_analyst back to the analyst node
                else:
                    candidate["status"] = "quarantined"
                    candidate["quarantine_reason"] = "risk_review_failed_max_retries"
                    risk_reviews[cid] = {
                        "status": "quarantined",
                        "retries": retries,
                        "reasons": result.rejection_reasons,
                    }

                    logger.warning(
                        f"Candidate {cid} quarantined after {retries} risk review retries. Reasons: {result.rejection_reasons}"
                    )
            else:
                candidate["status"] = "publish_ready"
                risk_reviews[cid] = {
                    "status": "passed",
                    "retries": retries,
                    "confidence": result.confidence_in_review,
                    "unsupported_claims": [],
                }
        except Exception as e:
            logger.error(f"Risk review failed for {cid}: {e}")
            state["errors"].append(f"Risk review failed for {cid}: {e}")
            # Fail closed: quarantine on error
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "risk_review_system_error"

    state["risk_reviews"] = risk_reviews

    if needs_retry:
        return {**state, "current_step": "extraction"}

    return {**state, "current_step": "draft_assembly"}


def draft_assembly_node(state: Phase2WorkflowState) -> Phase2WorkflowState:
    """Assemble export-ready Markdown and JSON."""
    logger.info("Executing draft assembly node")
    export_ready_candidates = []
    for candidate in state["candidates"]:
        if candidate.get("status") != "publish_ready":
            continue
        cid = candidate["candidate_id"]
        score_payload = state.get("scores", {}).get(cid)
        extraction_payload = state.get("extraction_results", {}).get(cid, {})
        evidence_snippets = extraction_payload.get("evidence_snippets", {})
        if not score_payload or score_payload.get("status") != "approved":
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "missing_approved_score"
            state["warnings"].append(
                f"Excluded {cid} from export: missing approved score."
            )
            continue
        if not evidence_snippets:
            candidate["status"] = "quarantined"
            candidate["quarantine_reason"] = "missing_evidence"
            state["warnings"].append(f"Excluded {cid} from export: missing evidence.")
            continue
        enrichment_claims = (
            state.get("enrichment_results", {}).get(cid, {}).get("claims", [])
        )
        factual_fields = {}
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
            state.get("risk_reviews", {}).get(cid, {}).get("confidence")
        )
        candidate["evidence_summary"] = evidence_snippets
        candidate["enrichment_claims"] = enrichment_claims
        candidate["unsupported_claims"] = (
            state.get("risk_reviews", {}).get(cid, {}).get("unsupported_claims", [])
        )
        candidate["content_sections"] = {
            "facts": factual_fields,
            "inferences": enrichment_claims,
            "editorial": {
                "score": score_payload,
                "thesis": f"Ranked from deterministic score for {candidate.get('company_name', 'Unknown Company')}.",
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
    state["issue_draft"] = {
        "title": "Weekly Berlin Insolvency Radar",
        "source_run_id": state.get("source_run_id"),
        "generated_at": datetime.now(UTC).isoformat(),
        "warnings": list(state.get("warnings", [])),
        "audit_summary": {
            "source_run_id": state.get("source_run_id"),
            "total_raw_records": len(state.get("raw_records", [])),
            "total_candidates": total_candidates,
            "publish_ready_candidates": len(export_ready_candidates),
            "quarantined_candidates": quarantined_candidates,
            "error_count": len(state.get("errors", [])),
            "warning_count": len(state.get("warnings", [])),
            "current_step": "draft_assembly",
        },
        "candidates": export_ready_candidates,
    }
    state["current_step"] = "export"
    return {**state}


def export_node(state: Phase2WorkflowState) -> Phase2WorkflowState:
    """Final export gate and persistence."""
    logger.info("Executing export node")

    settings = get_settings()
    export_dir = settings.data_dir / "exports"

    issue_data = state.get("issue_draft", {})

    # Generate Markdown
    md_path = generate_markdown_draft(issue_data, export_dir)

    # Generate JSON
    json_path = generate_json_package(issue_data, export_dir)

    # Return new state dictionary to ensure proper LangGraph checkpointing
    return {
        **state,
        "export_path": md_path,
        "warnings": state.get("warnings", [])
        + [f"Exported to {md_path} and {json_path}"],
        "current_step": "completed",
    }


def build_phase2_workflow() -> StateGraph:
    """Builds the Phase 2 LangGraph workflow."""
    workflow = StateGraph(Phase2WorkflowState)

    workflow.add_node("ingest", ingest_node)
    workflow.add_node("normalize_and_compliance", normalize_and_compliance_node)
    workflow.add_node("dedupe", dedupe_node)
    workflow.add_node("extraction", extraction_node)
    workflow.add_node("enrichment", enrichment_node)
    workflow.add_node("scoring", scoring_node)
    workflow.add_node("risk_review", risk_review_node)
    workflow.add_node("draft_assembly", draft_assembly_node)
    workflow.add_node("export", export_node)

    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "normalize_and_compliance")
    workflow.add_edge("normalize_and_compliance", "dedupe")
    workflow.add_edge("dedupe", "extraction")
    workflow.add_edge("extraction", "enrichment")
    workflow.add_edge("enrichment", "scoring")
    workflow.add_edge("scoring", "risk_review")

    # Conditional edge for risk review retry
    def review_router(
        state: Phase2WorkflowState,
    ) -> Literal["extraction", "draft_assembly"]:
        # Fixed: Check 'current_step' which is what risk_review_node updates
        if state.get("current_step") == "extraction":
            return "extraction"
        return "draft_assembly"

    workflow.add_conditional_edges(
        "risk_review",
        review_router,
        {"extraction": "extraction", "draft_assembly": "draft_assembly"},
    )

    workflow.add_edge("draft_assembly", "export")
    workflow.add_edge("export", END)

    return workflow
