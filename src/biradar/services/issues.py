"""Issue service for generating and exporting newsletter drafts."""

import logging
import uuid
from pathlib import Path
from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.db import Database, compute_content_hash
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
        try:
            if tier not in ("free", "paid"):
                audit_id = self.audit_repo.log_event(
                    actor=actor,
                    action="issue_draft_failed",
                    entity_type="issue",
                    entity_id="new",
                    request_data={
                        "week": week,
                        "tier": tier,
                        "candidate_ids": candidate_ids,
                    },
                    result_data={"error": "invalid_tier"},
                )
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "INVALID_TIER",
                            "message": "Tier must be 'free' or 'paid'",
                            "retryable": False,
                        }
                    ],
                    audit_id=audit_id,
                )

            candidates_data = []
            warnings = []

            for cid in candidate_ids:
                candidate = self.candidate_repo.get_by_id(cid)
                if not candidate:
                    warnings.append(f"Candidate {cid} not found, skipped.")
                    continue

                if candidate["status"] != "publish_ready":
                    warnings.append(
                        f"Candidate {cid} is not publish_ready (status: {candidate['status']}), skipped."
                    )
                    continue

                score = self.score_repo.get_latest_approved_for_candidate(cid)
                if not score:
                    warnings.append(f"Candidate {cid} has no approved score, skipped.")
                    continue

                evidence = self.evidence_repo.get_for_candidate(cid)
                if not evidence:
                    warnings.append(f"Candidate {cid} has no evidence, skipped.")
                    continue

                # Suppress admin contact in free tier
                filtered_evidence = []
                for ev in evidence:
                    if tier == "free" and "admin" in ev["field"].lower():
                        continue
                    filtered_evidence.append(ev)

                if not filtered_evidence:
                    warnings.append(
                        f"Candidate {cid} has no publishable evidence for {tier} tier, skipped."
                    )
                    continue

                candidates_data.append(
                    {
                        "candidate": candidate,
                        "score": score,
                        "evidence": filtered_evidence,
                    }
                )

            if not candidates_data:
                audit_id = self.audit_repo.log_event(
                    actor=actor,
                    action="issue_draft_failed",
                    entity_type="issue",
                    entity_id="new",
                    request_data={
                        "week": week,
                        "tier": tier,
                        "candidate_ids": candidate_ids,
                    },
                    result_data={
                        "error": "no_valid_candidates",
                        "warnings": warnings,
                    },
                )
                return ResultEnvelope(
                    ok=False,
                    warnings=warnings,
                    errors=[
                        {
                            "code": "NO_VALID_CANDIDATES",
                            "message": "No valid, approved candidates provided for draft.",
                            "retryable": False,
                        }
                    ],
                    audit_id=audit_id,
                )

            # Generate Markdown
            md_lines = [
                f"# {title}",
                f"**Week:** {week} | **Tier:** {tier.capitalize()}",
                "",
                "---",
                "",
            ]

            for idx, item in enumerate(candidates_data, start=1):
                cand = item["candidate"]
                score = item["score"]
                cat_emoji = (
                    "🔥"
                    if score["category"] == "hot"
                    else "✅"
                    if score["category"] == "solid"
                    else "👀"
                )

                md_lines.append(
                    f"### {cat_emoji} #{idx} — {cand['canonical_company_name']} ({cand['legal_form']})"
                )
                md_lines.append(f"- **Court:** {cand['court'] or 'N/A'}")
                md_lines.append(f"- **Case Number:** {cand['case_number'] or 'N/A'}")
                md_lines.append(
                    f"- **Opportunity Score:** {score['computed_score']} ({score['category'].replace('_', ' ').title()})"
                )
                md_lines.append(
                    f"- **Source:** {item['evidence'][0]['source_url'] if item['evidence'] else 'N/A'}"
                )
                md_lines.append("")

            if include_disclaimer:
                md_lines.extend(
                    [
                        "---",
                        "**Disclaimer:** This newsletter is for informational purposes only and does not constitute financial or investment advice. All data is sourced from public registers.",
                    ]
                )

            draft_markdown = "\n".join(md_lines)
            issue_id = f"issue_{uuid.uuid4().hex}"

            # Persist draft
            self.issue_repo.create_issue(
                issue_id=issue_id,
                week=week,
                tier=tier,
                title=title,
                draft_markdown=draft_markdown,
                created_by=actor,
            )

            # Link candidates to issue
            for idx, item in enumerate(candidates_data, start=1):
                self.issue_repo.link_candidate(
                    issue_id=issue_id,
                    candidate_id=item["candidate"]["candidate_id"],
                    rank=idx,
                    section="opportunity",
                    included_score_id=item["score"]["score_id"],
                )

            # Audit
            audit_id = self.audit_repo.log_event(
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

    def export_issue(
        self,
        issue_id: str,
        format: str = "markdown",
        actor: str = "system",
    ) -> ResultEnvelope[dict[str, Any]]:
        """Export an issue draft to a local file."""
        try:
            if format != "markdown":
                audit_id = self.audit_repo.log_event(
                    actor=actor,
                    action="issue_export_failed",
                    entity_type="issue",
                    entity_id=issue_id,
                    request_data={"format": format},
                    result_data={"error": "unsupported_format"},
                )
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "UNSUPPORTED_FORMAT",
                            "message": "Only 'markdown' format is supported in v0.",
                            "retryable": False,
                        }
                    ],
                    audit_id=audit_id,
                )

            issue = self.issue_repo.get_issue(issue_id)
            if not issue:
                audit_id = self.audit_repo.log_event(
                    actor=actor,
                    action="issue_export_failed",
                    entity_type="issue",
                    entity_id=issue_id,
                    request_data={"format": format},
                    result_data={"error": "issue_not_found"},
                )
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "ISSUE_NOT_FOUND",
                            "message": f"Issue {issue_id} not found.",
                            "retryable": False,
                        }
                    ],
                    audit_id=audit_id,
                )

            if issue["status"] != "draft":
                audit_id = self.audit_repo.log_event(
                    actor=actor,
                    action="issue_export_failed",
                    entity_type="issue",
                    entity_id=issue_id,
                    request_data={"format": format},
                    result_data={"error": "invalid_status", "status": issue["status"]},
                )
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "INVALID_STATUS",
                            "message": "Can only export drafts.",
                            "retryable": False,
                        }
                    ],
                    audit_id=audit_id,
                )

            # Generate filename
            filename = f"issue-{issue['week']}-{issue['tier']}.md"
            export_path = (self.export_dir / filename).resolve()
            if not str(export_path).startswith(str(self.export_dir.resolve())):
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

            # Write to disk
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Update issue status
            self.issue_repo.mark_exported(
                issue_id=issue_id, export_path=str(export_path)
            )

            # Audit
            audit_id = self.audit_repo.log_event(
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
