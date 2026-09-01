"""Export of the weekly issue draft when publish-ready candidates exist."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from biradar.storage.db import Database
from biradar.storage.repository import AuditRepository, IssueRepository


def _export_issue_when_ready(
    db: Database,
    final_state: dict[str, Any],
    score_ids: dict[str, str],
    export_path: str | None,
) -> str | None:
    """Create and mark the issue only when there is something publishable."""
    publish_ready_candidates = [
        candidate
        for candidate in final_state.get("issue_draft", {}).get("candidates", [])
        if candidate.get("status") == "publish_ready"
    ]
    if not publish_ready_candidates or not export_path:
        return None
    return _export_issue(
        db, final_state, publish_ready_candidates, score_ids, export_path
    )


def _export_issue(
    db: Database,
    final_state: dict[str, Any],
    publish_ready_candidates: list[dict[str, Any]],
    score_ids: dict[str, str],
    export_path: str,
) -> str | None:
    """Record the exported issue with its ranked candidates and audit trail."""
    issue_repo = IssueRepository(db)
    issue_id = f"issue_{uuid.uuid4().hex}"
    issue_repo.create_issue(
        issue_id=issue_id,
        week=datetime.now(UTC).strftime("%G-W%V"),
        tier="free",
        title=final_state.get("issue_draft", {}).get(
            "title", "Weekly Berlin Insolvency Radar"
        ),
        draft_markdown=Path(export_path).read_text(encoding="utf-8"),
        created_by="system:pipeline",
    )
    _link_ranked_candidates(issue_repo, issue_id, publish_ready_candidates, score_ids)
    issue_repo.mark_exported(issue_id, export_path)
    AuditRepository(db).log_event(
        actor="system:pipeline",
        action="pipeline_issue_exported",
        entity_type="issue",
        entity_id=issue_id,
        result_data={"export_path": export_path},
    )
    return issue_id


def _link_ranked_candidates(
    issue_repo: IssueRepository,
    issue_id: str,
    publish_ready_candidates: list[dict[str, Any]],
    score_ids: dict[str, str],
) -> None:
    for rank, candidate in enumerate(publish_ready_candidates, start=1):
        candidate_id = candidate["candidate_id"]
        issue_repo.link_candidate(
            issue_id=issue_id,
            candidate_id=candidate_id,
            rank=rank,
            section="ranked_opportunities",
            included_score_id=score_ids.get(candidate_id),
        )
