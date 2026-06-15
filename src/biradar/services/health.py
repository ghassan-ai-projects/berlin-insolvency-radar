"""Health service for application status checks."""

from typing import Any

from biradar.config.settings import AppConfig
from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.db import Database
from biradar.storage.repository import CandidateRepository, SourceRunRepository


class HealthService:
    def __init__(self, db: Database, config: AppConfig):
        self.db = db
        self.config = config
        self.candidate_repo = CandidateRepository(db)
        self.source_repo = SourceRunRepository(db)

    def check(self) -> ResultEnvelope[dict[str, Any]]:
        """Check application health and readiness."""
        try:
            counts = self.candidate_repo.get_counts_by_status()
            latest_run = self.source_repo.get_latest_successful_run()
            schema_version = self.db.get_schema_version()

            next_action = (
                "No data yet. Run radar_import_legacy_scout or add manual records."
            )
            if counts.get("needs_review", 0) > 0:
                next_action = f"Review {counts.get('needs_review', 0)} candidates awaiting review."
            elif counts.get("review_ready", 0) > 0:
                next_action = f"Approve {counts.get('review_ready', 0)} candidates ready for scoring."

            data = {
                "status": "ok",
                "database": {
                    "connected": True,
                    "path": str(self.db.db_path),
                    "schema_version": schema_version,
                },
                "counts": counts,
                "last_successful_source_run": latest_run["started_at"]
                if latest_run
                else None,
                "stale_sources": [],
                "next_action": next_action,
            }

            return ResultEnvelope(ok=True, data=data, next_action=next_action)
        except Exception as e:
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "HEALTH_CHECK_FAILED",
                        "message": str(e),
                        "retryable": True,
                    }
                ],
            )
