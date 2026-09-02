"""Persistence of successful workflow outputs into DuckDB-owned product state."""

import hashlib
import uuid
from typing import Any

from biradar.services.pipeline.candidate_records import (
    _audit_candidate_processed,
    _persist_approved_score,
    _persist_enrichment,
    _persist_risk_review,
)
from biradar.services.pipeline.issue_export import _export_issue_when_ready
from biradar.storage.clock import utc_now_iso
from biradar.storage.db import Database
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    EvidenceRepository,
    ReviewRepository,
    ScoreRepository,
)


def _persist_results(
    db: Database,
    final_state: dict[str, Any],
    export_path: str | None,
) -> str | None:
    """Persist workflow outputs for every non-skipped candidate, then export."""
    score_ids = _persist_all_candidates(db, final_state)
    return _export_issue_when_ready(db, final_state, score_ids, export_path)


def _persist_all_candidates(
    db: Database, final_state: dict[str, Any]
) -> dict[str, str]:
    """Persist each candidate; return the score IDs for issue linking."""
    evidence_repo = EvidenceRepository(db)
    existing_evidence = evidence_repo.get_existing_fields(
        _pending_candidate_ids(final_state)
    )
    score_ids: dict[str, str] = {}
    for candidate in final_state.get("candidates", []):
        # Already-processed records have existing linked candidates — skip persistence.
        if candidate.get("quarantine_reason") == "already_processed":
            continue
        _persist_candidate(db, final_state, candidate, existing_evidence, score_ids)
    return score_ids


def _pending_candidate_ids(final_state: dict[str, Any]) -> list[str]:
    """List IDs of candidates that will actually be persisted this run."""
    return [
        c.get("candidate_id")
        for c in final_state.get("candidates", [])
        if c.get("quarantine_reason") != "already_processed" and c.get("candidate_id")
    ]


def _persist_candidate(
    db: Database,
    final_state: dict[str, Any],
    candidate: dict[str, Any],
    existing_evidence: set[tuple[str, str]],
    score_ids: dict[str, str],
) -> None:
    """Write one candidate with its evidence, enrichment, score, review, and audit."""
    candidate_id = _ensure_candidate_id(candidate)
    _upsert_candidate_with_lineage(CandidateRepository(db), candidate, candidate_id)
    _persist_evidence(
        EvidenceRepository(db), final_state, candidate, candidate_id, existing_evidence
    )
    _persist_enrichment(db, final_state, candidate_id)
    _persist_approved_score(ScoreRepository(db), final_state, candidate_id, score_ids)
    _persist_risk_review(ReviewRepository(db), final_state, candidate, candidate_id)
    _audit_candidate_processed(
        AuditRepository(db), final_state, candidate, candidate_id
    )


def _ensure_candidate_id(candidate: dict[str, Any]) -> str:
    """Assign an ID to the candidate dict in place when the workflow left none."""
    candidate_id = candidate.get("candidate_id") or f"cand_{uuid.uuid4().hex}"
    candidate["candidate_id"] = candidate_id
    return candidate_id


def _upsert_candidate_with_lineage(
    candidate_repo: CandidateRepository,
    candidate: dict[str, Any],
    candidate_id: str,
) -> None:
    """Upsert the candidate row and link it to its raw source record."""
    quarantine_reason = candidate.get("quarantine_reason")
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
        risk_flags=[quarantine_reason] if quarantine_reason else None,
    )
    if candidate.get("raw_record_id"):
        candidate_repo.link_to_raw(
            candidate_id=candidate_id,
            raw_record_id=candidate["raw_record_id"],
            match_confidence=1.0,
            match_reason="pipeline_ingest",
        )


def _persist_evidence(
    evidence_repo: EvidenceRepository,
    final_state: dict[str, Any],
    candidate: dict[str, Any],
    candidate_id: str,
    existing_evidence: set[tuple[str, str]],
) -> None:
    """Insert one evidence item per extracted snippet not already stored."""
    extraction_result = final_state.get("extraction_results", {}).get(candidate_id, {})
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
            retrieved_at=utc_now_iso(),
            field=field,
            value=str(extraction_result.get(field) or candidate.get(field) or snippet),
            confidence=str(confidence_scores.get(field, 0.0)),
            trust_level="A",
            snippet=snippet,
            content_hash=hashlib.sha256(
                f"{candidate_id}:{field}:{snippet}".encode()
            ).hexdigest(),
        )
