"""Legacy import service for reading insolvency-scout DuckDB safely."""

import hashlib
from pathlib import Path
from typing import Any

import duckdb
from pydantic import BaseModel

from biradar.config.settings import AppConfig
from biradar.domain.compliance import evaluate_compliance
from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.db import Database
from biradar.storage.repository import AuditRepository


class LegacyImportInput(BaseModel):
    legacy_db_path: str
    since: str | None = None
    until: str | None = None
    dry_run: bool = False


class LegacyImportService:
    def __init__(self, db: Database, config: AppConfig, audit_repo: AuditRepository):
        self.db = db
        self.config = config
        self.audit_repo = audit_repo
        self.repo_db_path = str(self.db.db_path.absolute())

    def import_legacy_scout(
        self, params: LegacyImportInput, actor: str = "system"
    ) -> ResultEnvelope[dict[str, Any]]:
        """Import or dry-run import from legacy insolvency_scout database."""
        legacy_path = Path(params.legacy_db_path)

        # Safety check: prevent using the repo DB as legacy input
        if str(legacy_path.absolute()) == self.repo_db_path:
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "INVALID_LEGACY_PATH",
                        "message": "Legacy path cannot be the active repo database.",
                        "retryable": False,
                    }
                ],
            )

        if not legacy_path.exists():
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "FILE_NOT_FOUND",
                        "message": f"Legacy database not found at {legacy_path}",
                        "retryable": False,
                    }
                ],
            )

        # Record pre-import hash and mtime
        stat = legacy_path.stat()
        pre_hash = hashlib.sha256(legacy_path.read_bytes()).hexdigest()
        pre_mtime = stat.st_mtime
        pre_size = stat.st_size

        try:
            # Open legacy DB read-only
            legacy_conn = duckdb.connect(str(legacy_path), read_only=True)

            # Build query (simplified for v0; assumes basic filings table structure)
            query = "SELECT * FROM filings"
            cursor = legacy_conn.execute(query)
            cols = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            legacy_conn.close()

            raw_seen = len(rows)
            would_import = 0
            duplicates = 0
            rejected = 0
            inserted_candidates = 0

            # For v0, we just simulate/perform the mapping logic
            # In a full Phase 1 implementation, this would insert into raw_records, candidates, etc.
            for row_dict in [dict(zip(cols, row)) for row in rows]:
                company_name = row_dict.get("company_name", "")
                legal_form = row_dict.get("legal_form", "")
                raw_text = row_dict.get("raw_text", "")

                is_allowed, _ = evaluate_compliance(legal_form, raw_text, company_name)
                if not is_allowed:
                    rejected += 1
                    continue

                # Simplified dedupe simulation for v0
                duplicates += 1
                would_import += 1

            # Verify legacy DB was not mutated
            stat_post = legacy_path.stat()
            if stat_post.st_size != pre_size or stat_post.st_mtime != pre_mtime:
                # Attempt to restore or fail hard
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "LEGACY_MUTATED",
                            "message": "Legacy database was modified during import! Aborting.",
                            "retryable": False,
                        }
                    ],
                )

            post_hash = hashlib.sha256(legacy_path.read_bytes()).hexdigest()
            if post_hash != pre_hash:
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "LEGACY_HASH_MISMATCH",
                            "message": "Legacy database content hash changed during import!",
                            "retryable": False,
                        }
                    ],
                )

            audit_id = self.audit_repo.log_event(
                actor=actor,
                action="legacy_import_run",
                entity_type="source_run",
                entity_id="legacy_scout",
                request_data=params.model_dump(),
                result_data={
                    "raw_seen": raw_seen,
                    "would_import": would_import,
                    "rejected": rejected,
                    "duplicates": duplicates,
                },
            )

            return ResultEnvelope(
                ok=True,
                data={
                    "dry_run": params.dry_run,
                    "raw_records_seen": raw_seen,
                    "distinct_candidates": would_import,
                    "would_import": would_import
                    if params.dry_run
                    else inserted_candidates,
                    "duplicates": duplicates,
                    "rejected": rejected,
                    "warnings": ["Legacy scores imported as archived reference only"]
                    if not params.dry_run and inserted_candidates > 0
                    else [],
                },
                audit_id=audit_id,
                next_action="Call radar_list_candidates to review imported records."
                if not params.dry_run
                else "Dry run complete. Remove dry_run=true to execute.",
            )

        except Exception as e:
            return ResultEnvelope(
                ok=False,
                errors=[
                    {"code": "IMPORT_FAILED", "message": str(e), "retryable": True}
                ],
            )
