"""Service for executing the Phase 2 fully agentic pipeline."""

import logging
import os
import uuid
from asyncio import run as asyncio_run
from datetime import UTC, date, datetime
from pathlib import Path
import json
import hashlib

from biradar.config.settings import get_settings
from biradar.graph.phase2_workflow import build_phase2_workflow
from biradar.graph.checkpoints import CheckpointManager
from biradar.sources.official_portal import OfficialPortalAdapter
from biradar.storage.db import Database
from biradar.observability.logging import get_logger
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    EvidenceRepository,
    IssueRepository,
    ReviewRepository,
    ScoreRepository,
)

logger = get_logger(__name__)


def _load_dry_run_records(settings) -> tuple[str, list[dict]]:
    """Load fixture-backed source data for dry-run execution."""
    fixture_path = settings.project_root / "tests" / "fixtures" / "official_portal" / "sample_response.html"
    adapter = OfficialPortalAdapter(db=None)
    records = adapter._parse_response(fixture_path.read_text(encoding="utf-8"))
    return "dry_run_fixture", records


def _persist_phase2_results(
    db: Database,
    final_state: dict,
    export_path: str | None,
) -> str | None:
    """Persist successful Phase 2 workflow outputs into DuckDB-owned product state."""
    candidate_repo = CandidateRepository(db)
    evidence_repo = EvidenceRepository(db)
    score_repo = ScoreRepository(db)
    review_repo = ReviewRepository(db)
    issue_repo = IssueRepository(db)
    audit_repo = AuditRepository(db)

    score_ids: dict[str, str] = {}
    for candidate in final_state.get("candidates", []):
        candidate_id = candidate.get("candidate_id") or f"cand_{uuid.uuid4().hex}"
        candidate["candidate_id"] = candidate_id
        candidate_repo.upsert_candidate(
            candidate_id=candidate_id,
            company_name=candidate.get("company_name", "Unknown Company"),
            legal_form=candidate.get("legal_form"),
            court=candidate.get("court"),
            case_number=candidate.get("case_number"),
            register_number=candidate.get("register_number"),
            publication_date=candidate.get("publication_date"),
            publication_type=candidate.get("proceeding_stage"),
            status=candidate.get("status", "quarantined"),
            source_quality="A",
            risk_flags=[candidate.get("quarantine_reason")] if candidate.get("quarantine_reason") else None,
        )
        if candidate.get("raw_record_id"):
            candidate_repo.link_to_raw(
                candidate_id=candidate_id,
                raw_record_id=candidate["raw_record_id"],
                match_confidence=1.0,
                match_reason="phase2_ingest",
            )

        extraction_result = final_state.get("extraction_results", {}).get(candidate_id, {})
        evidence_snippets = extraction_result.get("evidence_snippets", {})
        confidence_scores = extraction_result.get("field_confidence_scores", {})
        for field, snippet in evidence_snippets.items():
            evidence_repo.insert_evidence(
                evidence_id=f"evid_{uuid.uuid4().hex}",
                candidate_id=candidate_id,
                source_provider="official_insolvency_portal",
                source_url=candidate.get("source_url"),
                retrieved_at=datetime.now(UTC).isoformat(),
                field=field,
                value=str(extraction_result.get(field) or candidate.get(field) or snippet),
                confidence=str(confidence_scores.get(field, 0.0)),
                trust_level="A",
                snippet=snippet,
                content_hash=hashlib.sha256(f"{candidate_id}:{field}:{snippet}".encode("utf-8")).hexdigest(),
            )

        score_payload = final_state.get("scores", {}).get(candidate_id)
        if score_payload and score_payload.get("status") == "approved":
            score_id = f"score_{uuid.uuid4().hex}"
            score_ids[candidate_id] = score_id
            score_repo.insert_score(
                score_id=score_id,
                candidate_id=candidate_id,
                score_version="v1",
                company_value=score_payload["company_value"],
                asset_quality=score_payload["asset_quality"],
                sector_attractiveness=score_payload["sector_attractiveness"],
                speed_of_action=score_payload["speed_of_action"],
                legal_risk=score_payload["legal_risk"],
                computed_score=score_payload["computed_score"],
                category=score_payload["category"],
                rationale_json=json.dumps(score_payload.get("rationale", {})),
                status="approved",
                reviewer="system:phase2_scoring",
            )

        risk_payload = final_state.get("risk_reviews", {}).get(candidate_id)
        if risk_payload:
            review_repo.insert_review(
                review_id=f"review_{uuid.uuid4().hex}",
                candidate_id=candidate_id,
                reviewer="system:risk_review",
                decision="approve" if risk_payload.get("status") == "passed" else "reject",
                from_status="deduped_candidate",
                to_status=candidate.get("status", "quarantined"),
                note=json.dumps(risk_payload, default=str),
            )

        audit_repo.log_event(
            actor="system:phase2_pipeline",
            action="phase2_candidate_processed",
            entity_type="candidate",
            entity_id=candidate_id,
            result_data={
                "status": candidate.get("status"),
                "source_run_id": final_state.get("source_run_id"),
            },
        )

    publish_ready_candidates = [
        candidate for candidate in final_state.get("issue_draft", {}).get("candidates", [])
        if candidate.get("status") == "publish_ready"
    ]
    if not publish_ready_candidates or not export_path:
        return None

    issue_id = f"issue_{uuid.uuid4().hex}"
    issue_title = final_state.get("issue_draft", {}).get("title", "Weekly Berlin Insolvency Radar")
    draft_markdown = Path(export_path).read_text(encoding="utf-8")
    issue_repo.create_issue(
        issue_id=issue_id,
        week=datetime.now(UTC).strftime("%G-W%V"),
        tier="free",
        title=issue_title,
        draft_markdown=draft_markdown,
        created_by="system:phase2_pipeline",
    )
    for rank, candidate in enumerate(publish_ready_candidates, start=1):
        candidate_id = candidate["candidate_id"]
        issue_repo.link_candidate(
            issue_id=issue_id,
            candidate_id=candidate_id,
            rank=rank,
            section="ranked_opportunities",
            included_score_id=score_ids.get(candidate_id),
        )
    issue_repo.mark_exported(issue_id, export_path)
    audit_repo.log_event(
        actor="system:phase2_pipeline",
        action="phase2_issue_exported",
        entity_type="issue",
        entity_id=issue_id,
        result_data={"export_path": export_path},
    )
    return issue_id


def run_phase2_pipeline(
    start_date: date,
    end_date: date,
    dry_run: bool = False,
    thread_id: str = "phase2_default",
) -> dict:
    """
    Execute the Phase 2 agentic workflow.
    
    Args:
        start_date: Start of the scrape window.
        end_date: End of the scrape window.
        dry_run: If True, do not persist to DuckDB.
        thread_id: LangGraph thread ID for checkpointing/resume.
        
    Returns:
        Execution summary and export paths.
    """
    logger.info(
        "Starting Phase 2 pipeline execution",
        extra={"start_date": str(start_date), "end_date": str(end_date), "dry_run": dry_run},
    )
    
    # Warn if no API key is present (agents will fall back to mock mode)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        logger.warning("DEEPSEEK_API_KEY not set. LLM agents will operate in mock/fallback mode.")
    
    settings = get_settings()
    db_path = settings.data_dir / "radar.duckdb"
    
    # 1. Initialize Database (skip if dry_run, though we might still want schema)
    if not dry_run:
        db = Database(db_path)
        db.run_migrations()
        checkpoint_db_path = settings.data_dir / "checkpoints.sqlite"
    else:
        db = Database(":memory:")
        db.run_migrations()
        checkpoint_db_path = ":memory:"
        
    # 2. Initialize Checkpoint Manager with appropriate path (prevents dry-run leakage)
    checkpoint_mgr = CheckpointManager(checkpoint_db_path)
    
    # 3. Acquire source data before graph execution.
    if dry_run:
        source_run_id, raw_records = _load_dry_run_records(settings)
    else:
        fetch_result = asyncio_run(
            OfficialPortalAdapter(db).fetch_date_range(
                start_date=start_date,
                end_date=end_date,
                dry_run=False,
            )
        )
        if fetch_result["status"] != "completed":
            return {
                "status": "failed",
                "error": "Official portal acquisition failed",
                "errors": fetch_result.get("errors", []),
            }
        source_run_id = fetch_result["source_run_id"]
        raw_records = fetch_result.get("records", [])

    # 4. Build and Compile Workflow
    workflow = build_phase2_workflow().compile(checkpointer=checkpoint_mgr.saver_instance)
    
    # 5. Define Initial State (transient execution data + metadata)
    initial_state = {
        "source_run_id": source_run_id,
        "raw_records": raw_records,
        "candidates": [],
        "extraction_results": {},
        "enrichment_results": {},
        "scores": {},
        "risk_reviews": {},
        "retry_counts": {},
        "current_step": "ingest",
        "errors": [],
        "warnings": [],
    }
    
    # 6. Execute Workflow
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Note: In a full implementation, the 'ingest' node would be passed 
        # the start_date/end_date via config or state. For now, we pass it in config.
        config["configurable"]["start_date"] = start_date
        config["configurable"]["end_date"] = end_date
        config["configurable"]["dry_run"] = dry_run
        
        final_state = workflow.invoke(initial_state, config)
        issue_id = None
        if not dry_run:
            issue_id = _persist_phase2_results(db, final_state, final_state.get("export_path"))
        
        logger.info("Phase 2 pipeline completed successfully")
        return {
            "status": "success",
            "current_step": final_state.get("current_step"),
            "export_path": final_state.get("export_path"),
            "issue_id": issue_id,
            "warnings": final_state.get("warnings", []),
            "errors": final_state.get("errors", []),
        }
        
    except Exception as e:
        logger.error("Phase 2 pipeline failed", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
        }
    finally:
        # Cleanup checkpoint connection if needed, or keep alive for app lifecycle
        pass
