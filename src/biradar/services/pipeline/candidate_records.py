"""Persistence of per-candidate derived records: enrichment, score, review, audit."""

import hashlib
import json
import uuid
from typing import Any

from biradar.storage.clock import utc_now_iso
from biradar.storage.repository import (
    AuditRepository,
    EnrichmentClaimRepository,
    EnrichmentRepository,
    ReviewRepository,
    ScoreRepository,
)


def _persist_enrichment(db, final_state: dict[str, Any], candidate_id: str) -> None:
    """Store the enrichment summary row and the source-normalized claims."""
    enrichment_result = final_state.get("enrichment_results", {}).get(candidate_id, {})
    _persist_enrichment_summary(
        EnrichmentRepository(db), enrichment_result, candidate_id
    )
    _persist_enrichment_claims(
        EnrichmentClaimRepository(db), enrichment_result, candidate_id
    )


def _persist_enrichment_summary(
    enrichment_repo: EnrichmentRepository,
    enrichment_result: dict[str, Any],
    candidate_id: str,
) -> None:
    enrichment_data = enrichment_result.get("data", {})
    if enrichment_data or enrichment_result.get("claims"):
        enrichment_repo.save_enrichment(
            candidate_id=candidate_id,
            sector=enrichment_data.get("sector"),
            funding_info=enrichment_data.get("funding_info"),
            tech_stack=enrichment_data.get("tech_stack"),
            website_url=enrichment_data.get("website_url"),
            website_status=str(enrichment_data.get("website_status"))
            if enrichment_data.get("website_status") is not None
            else None,
            github_org=enrichment_data.get("github_org"),
        )


def _persist_enrichment_claims(
    claim_repo: EnrichmentClaimRepository,
    enrichment_result: dict[str, Any],
    candidate_id: str,
) -> None:
    for claim in enrichment_result.get("claims", []):
        field = claim.get("field")
        value = claim.get("value")
        if not field or value is None:
            continue
        claim_repo.insert_claim(
            claim_id=f"claim_{uuid.uuid4().hex}",
            candidate_id=candidate_id,
            source_provider=str(claim.get("source_provider") or "unknown"),
            source_url=claim.get("source_url"),
            retrieved_at=utc_now_iso(),
            field=str(field),
            value=str(value),
            classification=(
                str(claim.get("classification"))
                if claim.get("classification") is not None
                else None
            ),
            note=str(claim.get("note")) if claim.get("note") is not None else None,
            content_hash=_claim_content_hash(candidate_id, claim),
        )


def _claim_content_hash(candidate_id: str, claim: dict[str, Any]) -> str:
    """Hash the claim identity so duplicate claims dedupe across runs."""
    return hashlib.sha256(
        (
            f"{candidate_id}:{claim.get('source_url')}:{claim.get('field')}:"
            f"{claim.get('value')}:{claim.get('classification')}:{claim.get('note')}"
        ).encode()
    ).hexdigest()


def _persist_approved_score(
    score_repo: ScoreRepository,
    final_state: dict[str, Any],
    candidate_id: str,
    score_ids: dict[str, str],
) -> None:
    """Persist the score of an approved candidate and record its ID."""
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


def _persist_risk_review(
    review_repo: ReviewRepository,
    final_state: dict[str, Any],
    candidate: dict[str, Any],
    candidate_id: str,
) -> None:
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


def _audit_candidate_processed(
    audit_repo: AuditRepository,
    final_state: dict[str, Any],
    candidate: dict[str, Any],
    candidate_id: str,
) -> None:
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
