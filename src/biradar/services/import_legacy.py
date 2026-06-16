"""Legacy import service for reading insolvency-scout DuckDB safely."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from pydantic import BaseModel

from biradar.config.settings import AppConfig
from biradar.domain.compliance import evaluate_compliance
from biradar.domain.dedupe import compute_dedupe_key
from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.db import Database, compute_content_hash
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    EvidenceRepository,
    RawRecordRepository,
    SourceRunRepository,
)


class LegacyImportInput(BaseModel):
    legacy_db_path: str
    since: str | None = None
    until: str | None = None
    dry_run: bool = True
    actor: str = "system"


class LegacyImportService:
    def __init__(self, db: Database, config: AppConfig, audit_repo: AuditRepository):
        self.db = db
        self.config = config
        self.audit_repo = audit_repo
        self.repo_db_path = str(self.db.db_path.absolute())

        # Repositories for import operations
        self.raw_repo = RawRecordRepository(db)
        self.candidate_repo = CandidateRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.source_run_repo = SourceRunRepository(db)

    def import_legacy_scout(
        self, params: LegacyImportInput
    ) -> ResultEnvelope[dict[str, Any]]:
        """Import or dry-run import from legacy insolvency_scout database."""
        legacy_path = Path(params.legacy_db_path)
        failure_code = "IMPORT_FAILED"
        source_run_id = f"run_{uuid.uuid4().hex}"
        transaction_started = False

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

        # Record pre-import hash and mtime (chunked to avoid OOM on large files)
        stat = legacy_path.stat()
        h = hashlib.sha256()
        with open(legacy_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        pre_hash = h.hexdigest()
        pre_mtime = stat.st_mtime
        pre_size = stat.st_size

        try:
            # Open legacy DB read-only
            legacy_conn = duckdb.connect(str(legacy_path), read_only=True)

            # Build query
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
            warnings: list[str] = []

            # If dry run, don't write anything
            if params.dry_run:
                seen_keys: set[str] = set()
                for row_dict in [dict(zip(cols, row)) for row in rows]:
                    company_name = str(row_dict.get("company_name", "") or "")
                    legal_form = str(row_dict.get("legal_form", "") or "")
                    raw_text = str(row_dict.get("raw_text", "") or "")
                    court = str(row_dict.get("court", "") or "")
                    case_number = str(row_dict.get("case_number", "") or "")
                    publication_date = str(row_dict.get("publication_date", "") or "")

                    is_allowed, reason = evaluate_compliance(
                        legal_form, raw_text, company_name
                    )
                    if not is_allowed:
                        rejected += 1
                        continue

                    dedupe_key = compute_dedupe_key(
                        company_name, court, case_number, publication_date
                    )
                    if dedupe_key in seen_keys or self.candidate_repo.get_by_id(
                        f"cand_{dedupe_key}"
                    ):
                        duplicates += 1
                        continue
                    seen_keys.add(dedupe_key)
                    would_import += 1

                    if not court or not case_number or not publication_date:
                        warnings.append(
                            f"Malformed row {row_dict.get('filing_id')}: missing court, case number, or publication date."
                        )

                stat_post = legacy_path.stat()
                post_hash = hashlib.sha256(legacy_path.read_bytes()).hexdigest()
                if (
                    stat_post.st_size != pre_size
                    or stat_post.st_mtime != pre_mtime
                    or post_hash != pre_hash
                ):
                    return ResultEnvelope(
                        ok=False,
                        errors=[
                            {
                                "code": "LEGACY_MUTATED",
                                "message": "Legacy database changed during dry-run import.",
                                "retryable": False,
                            }
                        ],
                    )

                return ResultEnvelope(
                    ok=True,
                    data={
                        "dry_run": True,
                        "raw_records_seen": raw_seen,
                        "distinct_candidates": would_import,
                        "would_import": would_import,
                        "duplicates": duplicates,
                        "rejected": rejected,
                        "warnings": warnings
                        + ["Dry run complete. No data was persisted."],
                    },
                    next_action="Remove dry_run=true to execute the import.",
                )

            # Real import
            self.db.begin()
            transaction_started = True
            self.source_run_repo.create_run(
                source_run_id=source_run_id,
                source_id="legacy_scout",
                run_type="batch_import",
                params_json=json.dumps(params.model_dump()),
            )

            imported_keys = set()

            for row_dict in [dict(zip(cols, row)) for row in rows]:
                company_name = str(row_dict.get("company_name", "") or "")
                legal_form = str(row_dict.get("legal_form", "") or "")
                raw_text = str(row_dict.get("raw_text", "") or "")
                court = str(row_dict.get("court", "") or "")
                case_number = str(row_dict.get("case_number", "") or "")
                publication_date = str(row_dict.get("publication_date", "") or "")
                publication_type = str(row_dict.get("publication_type", "") or "")
                register_number = str(row_dict.get("register_number", "") or "")
                source_url = str(row_dict.get("source_url", "") or "")
                filing_id = str(
                    row_dict.get("filing_id", "") or f"leg_{uuid.uuid4().hex}"
                )
                scraped_at = str(
                    row_dict.get("scraped_at", "") or datetime.now(UTC).isoformat()
                )

                # 1. Compliance filter
                is_allowed, reason = evaluate_compliance(
                    legal_form, raw_text, company_name
                )
                if not is_allowed:
                    rejected += 1
                    continue

                # 2. Deduplication
                dedupe_key = compute_dedupe_key(
                    company_name, court, case_number, publication_date
                )
                candidate_id = f"cand_{dedupe_key}"

                raw_record_id = f"raw_{uuid.uuid4().hex}"
                content_hash = compute_content_hash(
                    json.dumps(row_dict, sort_keys=True)
                )
                retrieved_at = (
                    scraped_at if scraped_at else datetime.now(UTC).isoformat()
                )
                persisted_raw_record_id = self.raw_repo.upsert_raw_record(
                    raw_record_id=raw_record_id,
                    source_run_id=source_run_id,
                    source_id="legacy_scout",
                    external_id=filing_id,
                    retrieved_at=retrieved_at,
                    source_url=source_url or None,
                    raw_text=raw_text or None,
                    raw_json=json.dumps(row_dict),
                    content_hash=content_hash,
                )

                existing = self.candidate_repo.get_by_id(candidate_id)
                duplicate_in_run = dedupe_key in imported_keys
                if existing or duplicate_in_run:
                    duplicates += 1
                    self.candidate_repo.link_to_raw(
                        candidate_id=candidate_id,
                        raw_record_id=persisted_raw_record_id,
                        match_confidence=1.0,
                        match_reason="duplicate_import_from_legacy",
                    )
                    continue
                imported_keys.add(dedupe_key)

                # 4. Determine status
                if not court or not case_number or not publication_date:
                    status = "needs_review"
                    risk_flags = ["malformed_source_row"]
                    warnings.append(
                        f"Malformed row {filing_id}: missing court, case number, or publication date."
                    )
                elif not legal_form or legal_form.strip() == "":
                    status = "needs_review"
                    risk_flags = ["missing_legal_form"]
                else:
                    status = "review_ready"
                    risk_flags = []

                # 5. Upsert candidate
                self.candidate_repo.upsert_candidate(
                    candidate_id=candidate_id,
                    company_name=company_name,
                    legal_form=legal_form or None,
                    court=court or None,
                    case_number=case_number or None,
                    register_number=register_number or None,
                    publication_date=publication_date or None,
                    publication_type=publication_type or None,
                    status=status,
                    source_quality="C",
                    risk_flags=risk_flags,
                )

                # 6. Link candidate to raw record
                self.candidate_repo.link_to_raw(
                    candidate_id=candidate_id,
                    raw_record_id=persisted_raw_record_id,
                    match_confidence=1.0,
                    match_reason="direct_import_from_legacy",
                )

                # 7. Insert evidence items for key fields
                evidence_fields = [
                    ("company_name", company_name),
                    ("court", court),
                    ("case_number", case_number),
                ]
                for field, value in evidence_fields:
                    if value:
                        ev_id = f"ev_{uuid.uuid4().hex}"
                        self.evidence_repo.insert_evidence(
                            evidence_id=ev_id,
                            candidate_id=candidate_id,
                            source_provider="legacy_scout",
                            source_url=source_url or None,
                            retrieved_at=retrieved_at,
                            field=field,
                            value=str(value),
                            confidence="high",
                            trust_level="C",
                            snippet=f"Imported: {field} = {value}",
                            content_hash=compute_content_hash(str(value)),
                        )

                inserted_candidates += 1

            # Mark source run complete
            self.source_run_repo.complete_run(
                source_run_id=source_run_id,
                records_seen=raw_seen,
                records_imported=inserted_candidates,
                duplicates=duplicates,
                rejected=rejected,
            )

            # Verify legacy DB was not mutated
            stat_post = legacy_path.stat()
            if stat_post.st_size != pre_size or stat_post.st_mtime != pre_mtime:
                failure_code = "LEGACY_MUTATED"
                raise RuntimeError("Legacy database was modified during import.")

            post_hash = hashlib.sha256(legacy_path.read_bytes()).hexdigest()
            if post_hash != pre_hash:
                failure_code = "LEGACY_HASH_MISMATCH"
                raise RuntimeError(
                    "Legacy database content hash changed during import."
                )

            self.db.commit()
            transaction_started = False

            audit_id = self.audit_repo.log_event(
                actor=params.actor,
                action="legacy_import_completed",
                entity_type="source_run",
                entity_id=source_run_id,
                request_data=params.model_dump(),
                result_data={
                    "raw_seen": raw_seen,
                    "inserted_candidates": inserted_candidates,
                    "rejected": rejected,
                    "duplicates": duplicates,
                    "warnings": warnings,
                },
            )

            return ResultEnvelope(
                ok=True,
                data={
                    "dry_run": False,
                    "raw_records_seen": raw_seen,
                    "distinct_candidates": inserted_candidates,
                    "would_import": inserted_candidates,
                    "duplicates": duplicates,
                    "rejected": rejected,
                    "warnings": warnings,
                },
                audit_id=audit_id,
                next_action="Call radar_list_candidates to review imported records.",
            )

        except Exception as e:
            if transaction_started:
                self.db.rollback()
            if not params.dry_run:
                self.source_run_repo.create_run(
                    source_run_id=source_run_id,
                    source_id="legacy_scout",
                    run_type="batch_import",
                    params_json=json.dumps(params.model_dump()),
                )
                self.source_run_repo.complete_run(
                    source_run_id=source_run_id,
                    records_seen=raw_seen if "raw_seen" in locals() else 0,
                    records_imported=0,
                    duplicates=0,
                    rejected=0,
                    error_json=str(e),
                )
            audit_id = self.audit_repo.log_event(
                actor=params.actor,
                action="legacy_import_failed",
                entity_type="source_run",
                entity_id=source_run_id,
                request_data=params.model_dump(),
                result_data={"error": str(e)},
            )
            return ResultEnvelope(
                ok=False,
                errors=[{"code": failure_code, "message": str(e), "retryable": False}],
                audit_id=audit_id,
            )
