"""Issue service facade: wires repositories to draft creation and export."""

import logging
from pathlib import Path
from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.services.issues.drafting import _create_draft
from biradar.services.issues.exporting import _export_issue
from biradar.storage.db import Database
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    EvidenceRepository,
    IssueRepository,
    ScoreRepository,
)

logger = logging.getLogger(__name__)


class IssueService:
    def __init__(self, db: Database, export_dir: str | Path):
        self.db = db
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.candidate_repo = CandidateRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.score_repo = ScoreRepository(db)
        self.issue_repo = IssueRepository(db)
        self.audit_repo = AuditRepository(db)

    def create_issue_draft(
        self,
        week: str,
        tier: str,
        candidate_ids: list[str],
        title: str,
        include_disclaimer: bool = True,
        actor: str = "system",
    ) -> ResultEnvelope[dict[str, Any]]:
        """Create a newsletter issue draft from approved candidates."""
        return _create_draft(
            self.audit_repo,
            self.candidate_repo,
            self.score_repo,
            self.evidence_repo,
            self.issue_repo,
            week=week,
            tier=tier,
            candidate_ids=candidate_ids,
            title=title,
            include_disclaimer=include_disclaimer,
            actor=actor,
        )

    def export_issue(
        self,
        issue_id: str,
        format: str = "markdown",
        actor: str = "system",
    ) -> ResultEnvelope[dict[str, Any]]:
        """Export an issue draft to a local file."""
        return _export_issue(
            self.audit_repo,
            self.issue_repo,
            self.export_dir,
            issue_id=issue_id,
            format=format,
            actor=actor,
        )
