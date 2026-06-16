"""Service entrypoints for the production workflow pipeline."""

import hashlib
import json
import tempfile
import uuid
from asyncio import run as asyncio_run
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from biradar.agents.extraction import ExtractionResult
from biradar.agents.risk_review import RiskReviewResult
from biradar.config.settings import get_settings, load_config
from biradar.graph.checkpoints import CheckpointManager
from biradar.graph.pipeline_workflow import build_pipeline_workflow
from biradar.observability.logging import get_logger
from biradar.sources.enrichment import EnrichmentResult, _reset_disabled_sources
from biradar.sources.official_portal import OfficialPortalAdapter
from biradar.storage.db import Database
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    EvidenceRepository,
    IssueRepository,
    RawRecordRepository,
    ReviewRepository,
    ScoreRepository,
    SourceRunRepository,
)

logger = get_logger(__name__)


def _load_fixture_records(settings: Any) -> tuple[str, list[dict[str, Any]]]:
    """Load fixture-backed source data for validation execution."""
    fixture_path = (
        settings.project_root
        / "tests"
        / "fixtures"
        / "official_portal"
        / "sample_response.html"
    )
    adapter = OfficialPortalAdapter(db=None)
    records = adapter._parse_response(fixture_path.read_text(encoding="utf-8"))
    return "fixture_validation_run", records


def _stub_extractor(raw_text: str, source_url: str) -> ExtractionResult:
    return ExtractionResult(
        company_name="Test Berlin GmbH",
        legal_form="GmbH",
        court="Amtsgericht Charlottenburg",
        case_number="36e IN 123/26",
        filing_date="2026-06-15",
        proceeding_stage="Eroeffnungsbeschluss",
        is_consumer_likely=False,
        field_confidence_scores={"company_name": 0.95, "case_number": 0.93},
        evidence_snippets={
            "company_name": "Test Berlin GmbH",
            "case_number": "36e IN 123/26",
        },
    )


def _stub_risk_reviewer(
    candidate_data: dict[str, Any],
    extraction_data: dict[str, Any],
    enrichment_data: dict[str, Any],
    draft_thesis: str,
) -> RiskReviewResult:
    return RiskReviewResult(
        passed_review=True,
        rejection_reasons=None,
        actionable_feedback_for_analyst=None,
        flagged_unsupported_claims=[],
        confidence_in_review=0.88,
    )


def _stub_enricher(company_name: str) -> EnrichmentResult:
    return EnrichmentResult(
        company_name=company_name,
        sources=[
            {
                "source": "validation_stub",
                "url": "https://example.com/company",
                "registry_number": "HRB 123456 B",
                "registry_court": "Amtsgericht Charlottenburg",
                "legal_form": "GmbH",
                "company_status": "active",
                "tech_stack": "Python, FastAPI",
                "github_org": "test-berlin",
                "funding_info": "Reports available",
            }
        ],
        errors=[],
        enriched=True,
        sector="Legal form: GmbH",
        tech_stack="Python, FastAPI",
        website_url="https://example.com/company",
        website_status=200,
        github_org="test-berlin",
        funding_info="Reports available",
        legal_form="GmbH",
        registry_court="Amtsgericht Charlottenburg",
        registry_number="HRB 123456 B",
        company_status="active",
    )


def _persist_results(
    db: Database,
    final_state: dict[str, Any],
    export_path: str | None,
) -> str | None:
    """Persist successful workflow outputs into DuckDB-owned product state."""
    candidate_repo = CandidateRepository(db)
    evidence_repo = EvidenceRepository(db)
    score_repo = ScoreRepository(db)
    review_repo = ReviewRepository(db)
    issue_repo = IssueRepository(db)
    audit_repo = AuditRepository(db)

    score_ids: dict[str, str] = {}
    # Batch pre-load existing evidence fields to skip redundant inserts on re-runs
    all_candidate_ids = [
        c.get("candidate_id")
        for c in final_state.get("candidates", [])
        if c.get("quarantine_reason") != "already_processed" and c.get("candidate_id")
    ]
    existing_evidence = evidence_repo.get_existing_fields(all_candidate_ids)

    for candidate in final_state.get("candidates", []):
        # Already-processed records have existing linked candidates — skip persistence.
        if candidate.get("quarantine_reason") == "already_processed":
            continue

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
            risk_flags=[candidate.get("quarantine_reason")]
            if candidate.get("quarantine_reason")
            else None,
        )
        if candidate.get("raw_record_id"):
            candidate_repo.link_to_raw(
                candidate_id=candidate_id,
                raw_record_id=candidate["raw_record_id"],
                match_confidence=1.0,
                match_reason="pipeline_ingest",
            )

        extraction_result = final_state.get("extraction_results", {}).get(
            candidate_id, {}
        )
        evidence_snippets = extraction_result.get("evidence_snippets", {})
        confidence_scores = extraction_result.get("field_confidence_scores", {})
        for field, snippet in evidence_snippets.items():
            if (candidate_id, field) in existing_evidence:
                continue  # already persisted from previous run
            evidence_repo.insert_evidence(
                evidence_id=f"evid_{uuid.uuid4().hex}",
                candidate_id=candidate_id,
                source_provider="official_insolvency_portal",
                source_url=candidate.get("source_url"),
                retrieved_at=datetime.now(UTC).isoformat(),
                field=field,
                value=str(
                    extraction_result.get(field) or candidate.get(field) or snippet
                ),
                confidence=str(confidence_scores.get(field, 0.0)),
                trust_level="A",
                snippet=snippet,
                content_hash=hashlib.sha256(
                    f"{candidate_id}:{field}:{snippet}".encode()
                ).hexdigest(),
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
                reviewer="system:pipeline_scoring",
            )

        risk_payload = final_state.get("risk_reviews", {}).get(candidate_id)
        if risk_payload:
            review_repo.insert_review(
                review_id=f"review_{uuid.uuid4().hex}",
                candidate_id=candidate_id,
                reviewer="system:risk_review",
                decision="approve"
                if risk_payload.get("status") == "passed"
                else "reject",
                from_status="deduped_candidate",
                to_status=candidate.get("status", "quarantined"),
                note=json.dumps(risk_payload, default=str),
            )

        audit_repo.log_event(
            actor="system:pipeline",
            action="pipeline_candidate_processed",
            entity_type="candidate",
            entity_id=candidate_id,
            result_data={
                "status": candidate.get("status"),
                "source_run_id": final_state.get("source_run_id"),
            },
        )

    publish_ready_candidates = [
        candidate
        for candidate in final_state.get("issue_draft", {}).get("candidates", [])
        if candidate.get("status") == "publish_ready"
    ]
    if not publish_ready_candidates or not export_path:
        return None

    issue_id = f"issue_{uuid.uuid4().hex}"
    issue_title = final_state.get("issue_draft", {}).get(
        "title", "Weekly Berlin Insolvency Radar"
    )
    issue_repo.create_issue(
        issue_id=issue_id,
        week=datetime.now(UTC).strftime("%G-W%V"),
        tier="free",
        title=issue_title,
        draft_markdown=Path(export_path).read_text(encoding="utf-8"),
        created_by="system:pipeline",
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
        actor="system:pipeline",
        action="pipeline_issue_exported",
        entity_type="issue",
        entity_id=issue_id,
        result_data={"export_path": export_path},
    )
    return issue_id


def run_pipeline(
    start_date: date,
    end_date: date,
    dry_run: bool = False,
    thread_id: str = "pipeline_default",
    db_path: str | Path | None = None,
    source_mode: str | None = None,
    extractor: Any | None = None,
    risk_reviewer: Any | None = None,
    enricher: Any | None = None,
) -> dict[str, Any]:
    """Execute the agentic workflow pipeline."""
    logger.info(
        "Starting pipeline execution",
        extra={
            "start_date": str(start_date),
            "end_date": str(end_date),
            "dry_run": dry_run,
        },
    )

    settings = get_settings()
    config = load_config(settings.project_root / "config")
    target_db_path = Path(db_path) if db_path else settings.data_dir / "radar.duckdb"
    official_source_cfg = config.sources.get("official_insolvency_berlin")
    effective_source_mode = source_mode or (
        official_source_cfg.mode if official_source_cfg else "normal"
    )

    if dry_run:
        db = Database(":memory:")
        checkpoint_db_path = ":memory:"
    else:
        db = Database(target_db_path)
        checkpoint_db_path = settings.data_dir / "checkpoints.sqlite"
    db.run_migrations()
    checkpoint_mgr = CheckpointManager(checkpoint_db_path)

    try:
        if dry_run:
            source_run_id, raw_records = _load_fixture_records(settings)
        elif effective_source_mode == "fixture":
            fixture_path = (
                Path(official_source_cfg.path)
                if official_source_cfg and official_source_cfg.path
                else settings.project_root
                / "tests"
                / "fixtures"
                / "official_portal"
                / "sample_response.html"
            )
            fetch_result = OfficialPortalAdapter(db).fetch_fixture_date_range(
                fixture_path=str(fixture_path),
                start_date=start_date,
                end_date=end_date,
                dry_run=False,
            )
            if fetch_result["status"] != "completed":
                return {
                    "status": "failed",
                    "error": "Official portal fixture acquisition failed",
                    "errors": fetch_result.get("errors", []),
                }
            source_run_id = fetch_result["source_run_id"]
            raw_records = fetch_result.get("records", [])
        else:
            # Check if we already have a completed run covering this date window.
            # If so, reuse cached records instead of hitting the live portal again.
            source_id = "official_insolvency_berlin"
            source_run_repo = SourceRunRepository(db)
            covering_run_id = source_run_repo.find_covering_run(
                source_id,
                start_date.isoformat(),
                end_date.isoformat(),
            )
            if covering_run_id:
                raw_record_repo = RawRecordRepository(db)
                cached_records = raw_record_repo.list_by_source_run(covering_run_id)
                if cached_records:
                    source_run_id = covering_run_id
                    raw_records = cached_records
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

        if not dry_run:
            AuditRepository(db).log_event(
                actor="system:pipeline",
                action="pipeline_acquisition_completed"
                if raw_records is not None
                else "pipeline_acquisition_attempted",
                entity_type="source_run",
                entity_id=source_run_id,
                request_data={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "source_mode": effective_source_mode,
                },
                result_data={"raw_records": len(raw_records)},
            )

        _reset_disabled_sources()

        workflow = build_pipeline_workflow(
            extractor=extractor,
            risk_reviewer=risk_reviewer,
            enricher=enricher,
        ).compile(checkpointer=checkpoint_mgr.saver_instance)

        # Collect raw_record_ids that already have linked candidates in the DB.
        # These records skip extraction + enrichment on re-runs.
        already_processed_ids: list[str] = []
        if not dry_run and raw_records:
            raw_ids = [r.get("raw_record_id") for r in raw_records if r.get("raw_record_id")]
            if raw_ids:
                placeholders = ",".join("?" * len(raw_ids))
                already_processed_ids = [
                    row[0]
                    for row in db.conn.execute(
                        f"SELECT DISTINCT raw_record_id FROM candidate_sources WHERE raw_record_id IN ({placeholders})",
                        raw_ids,
                    ).fetchall()
                ]

        initial_state = {
            "source_run_id": source_run_id,
            "raw_records": raw_records,
            "already_processed_raw_ids": already_processed_ids,
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
        invocation_config = {
            "configurable": {
                "thread_id": thread_id,
                "start_date": start_date,
                "end_date": end_date,
                "dry_run": dry_run,
            }
        }
        final_state = workflow.invoke(initial_state, invocation_config)
        issue_id = None
        if not dry_run:
            issue_id = _persist_results(db, final_state, final_state.get("export_path"))

        logger.info("Pipeline completed successfully")
        return {
            "status": "success",
            "current_step": final_state.get("current_step"),
            "export_path": final_state.get("export_path"),
            "issue_id": issue_id,
            "warnings": final_state.get("warnings", []),
            "errors": final_state.get("errors", []),
        }
    except Exception as exc:
        logger.error("Pipeline failed", exc_info=True)
        return {"status": "failed", "error": str(exc)}
    finally:
        checkpoint_mgr.close()
        db.close()


def run_pipeline_check() -> dict[str, Any]:
    """Run a full local verification pass against fixture-backed acquisition and deterministic stubs."""
    start_date = date(2026, 6, 10)
    end_date = date(2026, 6, 16)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "pipeline_check.duckdb"
        first = run_pipeline(
            start_date=start_date,
            end_date=end_date,
            dry_run=False,
            thread_id="pipeline_check_first",
            db_path=db_path,
            source_mode="fixture",
            extractor=_stub_extractor,
            risk_reviewer=_stub_risk_reviewer,
            enricher=_stub_enricher,
        )
        second = run_pipeline(
            start_date=start_date,
            end_date=end_date,
            dry_run=False,
            thread_id="pipeline_check_second",
            db_path=db_path,
            source_mode="fixture",
            extractor=_stub_extractor,
            risk_reviewer=_stub_risk_reviewer,
            enricher=_stub_enricher,
        )
        db = Database(db_path)
        try:
            counts = {
                "source_runs": db.conn.execute(
                    "SELECT COUNT(*) FROM source_runs"
                ).fetchone()[0],
                "raw_records": db.conn.execute(
                    "SELECT COUNT(*) FROM raw_records"
                ).fetchone()[0],
                "candidates": db.conn.execute(
                    "SELECT COUNT(*) FROM candidates"
                ).fetchone()[0],
                "publish_ready": db.conn.execute(
                    "SELECT COUNT(*) FROM candidates WHERE status = 'publish_ready'"
                ).fetchone()[0],
                "issues": db.conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0],
            }
        finally:
            db.close()
        return {
            "status": "success"
            if first["status"] == "success" and second["status"] == "success"
            else "failed",
            "first_run": first,
            "second_run": second,
            "counts": counts,
        }
