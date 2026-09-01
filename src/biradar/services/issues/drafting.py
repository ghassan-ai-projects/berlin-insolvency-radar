"""Newsletter draft creation: selection, rendering, persistence, audit."""

import logging
import uuid
from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.services.issues.audit_outcomes import _failure_envelope
from biradar.services.issues.rendering import _render_draft_markdown
from biradar.services.issues.selection import _collect_publishable_candidates
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    EvidenceRepository,
    IssueRepository,
    ScoreRepository,
)

logger = logging.getLogger(__name__)


def _create_draft(
    audit_repo: AuditRepository,
    candidate_repo: CandidateRepository,
    score_repo: ScoreRepository,
    evidence_repo: EvidenceRepository,
    issue_repo: IssueRepository,
    *,
    week: str,
    tier: str,
    candidate_ids: list[str],
    title: str,
    include_disclaimer: bool = True,
    actor: str = "system",
) -> ResultEnvelope[dict[str, Any]]:
    """Create a newsletter issue draft from approved candidates."""
    try:
        if tier not in ("free", "paid"):
            return _failure_envelope(
                audit_repo,
                actor=actor,
                action="issue_draft_failed",
                entity_id="new",
                request_data={
                    "week": week,
                    "tier": tier,
                    "candidate_ids": candidate_ids,
                },
                result_data={"error": "invalid_tier"},
                code="INVALID_TIER",
                message="Tier must be 'free' or 'paid'",
            )

        candidates_data, warnings = _collect_publishable_candidates(
            candidate_repo, score_repo, evidence_repo, candidate_ids, tier
        )
        if not candidates_data:
            return _failure_envelope(
                audit_repo,
                actor=actor,
                action="issue_draft_failed",
                entity_id="new",
                request_data={
                    "week": week,
                    "tier": tier,
                    "candidate_ids": candidate_ids,
                },
                result_data={"error": "no_valid_candidates", "warnings": warnings},
                code="NO_VALID_CANDIDATES",
                message="No valid, approved candidates provided for draft.",
                warnings=warnings,
            )

        draft_markdown = _render_draft_markdown(
            title, week, tier, candidates_data, include_disclaimer
        )
        issue_id = f"issue_{uuid.uuid4().hex}"

        _persist_draft(
            issue_repo,
            issue_id,
            week,
            tier,
            title,
            actor,
            draft_markdown,
            candidates_data,
        )

        audit_id = audit_repo.log_event(
            actor=actor,
            action="issue_draft_created",
            entity_type="issue",
            entity_id=issue_id,
            request_data={
                "week": week,
                "tier": tier,
                "candidate_count": len(candidates_data),
            },
            result_data={"draft_length": len(draft_markdown)},
        )

        return ResultEnvelope(
            ok=True,
            data={
                "issue_id": issue_id,
                "status": "draft",
                "candidate_count": len(candidates_data),
                "markdown_preview": draft_markdown[:500] + "..."
                if len(draft_markdown) > 500
                else draft_markdown,
            },
            warnings=warnings,
            audit_id=audit_id,
            next_action="Call radar_export_issue to save this draft to disk.",
        )

    except Exception:
        logger.exception("Failed to create issue draft")
        return ResultEnvelope(
            ok=False,
            errors=[
                {
                    "code": "CREATE_DRAFT_FAILED",
                    "message": "Internal error creating draft.",
                    "retryable": True,
                }
            ],
        )


def _persist_draft(
    issue_repo: IssueRepository,
    issue_id: str,
    week: str,
    tier: str,
    title: str,
    actor: str,
    draft_markdown: str,
    candidates_data: list[dict[str, Any]],
) -> None:
    """Insert the issue row and link its candidates in rank order."""
    issue_repo.create_issue(
        issue_id=issue_id,
        week=week,
        tier=tier,
        title=title,
        draft_markdown=draft_markdown,
        created_by=actor,
    )
    for idx, item in enumerate(candidates_data, start=1):
        issue_repo.link_candidate(
            issue_id=issue_id,
            candidate_id=item["candidate"]["candidate_id"],
            rank=idx,
            section="opportunity",
            included_score_id=item["score"]["score_id"],
        )
