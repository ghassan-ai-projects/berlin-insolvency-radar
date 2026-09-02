"""Issue draft export to local files."""

import logging
from pathlib import Path
from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.services.issues.audit_outcomes import _failure_envelope
from biradar.storage.db import compute_content_hash
from biradar.storage.repository import AuditRepository, IssueRepository

logger = logging.getLogger(__name__)


def _export_issue(
    audit_repo: AuditRepository,
    issue_repo: IssueRepository,
    export_dir: Path,
    *,
    issue_id: str,
    format: str = "markdown",
    actor: str = "system",
) -> ResultEnvelope[dict[str, Any]]:
    """Export an issue draft to a local file."""
    try:
        if format != "markdown":
            return _failure_envelope(
                audit_repo,
                actor=actor,
                action="issue_export_failed",
                entity_id=issue_id,
                request_data={"format": format},
                result_data={"error": "unsupported_format"},
                code="UNSUPPORTED_FORMAT",
                message="Only 'markdown' format is supported in v0.",
            )

        issue = issue_repo.get_issue(issue_id)
        if not issue:
            return _failure_envelope(
                audit_repo,
                actor=actor,
                action="issue_export_failed",
                entity_id=issue_id,
                request_data={"format": format},
                result_data={"error": "issue_not_found"},
                code="ISSUE_NOT_FOUND",
                message=f"Issue {issue_id} not found.",
            )

        if issue["status"] != "draft":
            return _failure_envelope(
                audit_repo,
                actor=actor,
                action="issue_export_failed",
                entity_id=issue_id,
                request_data={"format": format},
                result_data={"error": "invalid_status", "status": issue["status"]},
                code="INVALID_STATUS",
                message="Can only export drafts.",
            )

        export_path = _export_path_for(export_dir, issue)
        if export_path is None:
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "EXPORT_FAILED",
                        "message": "Export path escapes export directory.",
                        "retryable": False,
                    }
                ],
            )

        content = issue["draft_markdown"]
        content_hash = compute_content_hash(content)

        with open(export_path, "w", encoding="utf-8") as f:
            f.write(content)

        issue_repo.mark_exported(issue_id=issue_id, export_path=str(export_path))

        audit_id = audit_repo.log_event(
            actor=actor,
            action="issue_exported",
            entity_type="issue",
            entity_id=issue_id,
            request_data={"format": format},
            result_data={
                "export_path": str(export_path),
                "content_hash": content_hash,
            },
        )

        return ResultEnvelope(
            ok=True,
            data={
                "path": str(export_path),
                "sha256": content_hash,
            },
            audit_id=audit_id,
            next_action="Draft exported successfully. Review the local Markdown file before any manual publishing.",
        )

    except Exception:
        logger.exception("Failed to export issue %s", issue_id)
        return ResultEnvelope(
            ok=False,
            errors=[
                {
                    "code": "EXPORT_FAILED",
                    "message": "Internal error exporting issue.",
                    "retryable": True,
                }
            ],
        )


def _export_path_for(export_dir: Path, issue: dict[str, Any]) -> Path | None:
    """Resolve the export file path, or None when it escapes the directory."""
    filename = f"issue-{issue['week']}-{issue['tier']}.md"
    export_path = (export_dir / filename).resolve()
    if not str(export_path).startswith(str(export_dir.resolve())):
        return None
    return export_path
