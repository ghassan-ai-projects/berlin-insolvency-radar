"""Issue service for generating and exporting newsletter drafts."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.db import Database, compute_content_hash
from biradar.storage.repository import AuditRepository, CandidateRepository


class IssueService:
    def __init__(self, db: Database, export_dir: str | Path):
        self.db = db
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.candidate_repo = CandidateRepository(db)
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
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "INVALID_TIER",
                            "message": "Tier must be 'free' or 'paid'",
                            "retryable": False,
                        }
                    ],
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

                # Fetch approved score
                score_cursor = self.db.conn.execute(
                    "SELECT * FROM scores WHERE candidate_id = ? AND status = 'approved' ORDER BY created_at DESC LIMIT 1",
                    [cid],
                )
                score_row = score_cursor.fetchone()
                if not score_row:
                    warnings.append(f"Candidate {cid} has no approved score, skipped.")
                    continue

                score_cols = [desc[0] for desc in score_cursor.description]
                score = dict(zip(score_cols, score_row))

                # Fetch evidence
                evidence_cursor = self.db.conn.execute(
                    "SELECT source_url, field, value FROM evidence_items WHERE candidate_id = ?",
                    [cid],
                )
                evidence_cols = [desc[0] for desc in evidence_cursor.description]
                evidence = [
                    dict(zip(evidence_cols, row)) for row in evidence_cursor.fetchall()
                ]

                # Suppress admin contact in free tier
                filtered_evidence = []
                for ev in evidence:
                    if tier == "free" and "admin" in ev["field"].lower():
                        continue
                    filtered_evidence.append(ev)

                candidates_data.append(
                    {
                        "candidate": candidate,
                        "score": score,
                        "evidence": filtered_evidence,
                    }
                )

            if not candidates_data:
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
            now_str = datetime.now(UTC).isoformat()

            # Persist draft
            self.db.conn.execute(
                """
                INSERT INTO issues 
                (issue_id, week, tier, status, title, draft_markdown, created_by, created_at)
                VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)
                """,
                [issue_id, week, tier, title, draft_markdown, actor, now_str],
            )

            # Link candidates to issue
            for idx, item in enumerate(candidates_data, start=1):
                self.db.conn.execute(
                    """
                    INSERT INTO issue_candidates (issue_id, candidate_id, rank, section, included_score_id)
                    VALUES (?, ?, ?, 'opportunity', ?)
                    """,
                    [
                        issue_id,
                        item["candidate"]["candidate_id"],
                        idx,
                        item["score"]["score_id"],
                    ],
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

        except Exception as e:
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "CREATE_DRAFT_FAILED",
                        "message": str(e),
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
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "UNSUPPORTED_FORMAT",
                            "message": "Only 'markdown' format is supported in v0.",
                            "retryable": False,
                        }
                    ],
                )

            cursor = self.db.conn.execute(
                "SELECT * FROM issues WHERE issue_id = ? LIMIT 1", [issue_id]
            )
            row = cursor.fetchone()
            if not row:
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "ISSUE_NOT_FOUND",
                            "message": f"Issue {issue_id} not found.",
                            "retryable": False,
                        }
                    ],
                )

            cols = [desc[0] for desc in cursor.description]
            issue = dict(zip(cols, row))

            if issue["status"] != "draft":
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "INVALID_STATUS",
                            "message": "Can only export drafts.",
                            "retryable": False,
                        }
                    ],
                )

            # Generate filename
            filename = f"issue-{issue['week']}-{issue['tier']}.md"
            export_path = self.export_dir / filename

            content = issue["draft_markdown"]
            content_hash = compute_content_hash(content)

            # Write to disk
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(content)

            now_str = datetime.now(UTC).isoformat()
            self.db.conn.execute(
                "UPDATE issues SET status = 'exported', exported_at = ?, export_path = ? WHERE issue_id = ?",
                [now_str, str(export_path), issue_id],
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
                next_action="Draft exported successfully. Review in beehiiv UI (manual step).",
            )

        except Exception as e:
            return ResultEnvelope(
                ok=False,
                errors=[
                    {"code": "EXPORT_FAILED", "message": str(e), "retryable": True}
                ],
            )
