"""Legacy import service: guards, fingerprinting, branch, audit, envelope."""

import json
import uuid
from pathlib import Path
from typing import Any

from biradar.config.settings import AppConfig
from biradar.mcp.envelope import ResultEnvelope
from biradar.services.import_legacy.dry_run import run_dry_run
from biradar.services.import_legacy.guards import _validate_legacy_path
from biradar.services.import_legacy.integrity import (
    FileFingerprint,
    LegacyIntegrityError,
    fingerprint_file,
    verify_import_snapshot,
)
from biradar.services.import_legacy.models import LegacyImportInput
from biradar.services.import_legacy.persistence import (
    ImportOutcome,
    persist_import_rows,
)
from biradar.storage.db import Database
from biradar.storage.legacy_reader import read_filings_read_only
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    EvidenceRepository,
    RawRecordRepository,
    SourceRunRepository,
)


class _Transaction:
    """Tracks whether the repo transaction is open so failures roll back once."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._started = False

    def begin(self) -> None:
        self._db.begin()
        self._started = True

    def commit(self) -> None:
        self._db.commit()
        self._started = False

    def rollback_if_started(self) -> None:
        if self._started:
            self._db.rollback()


def _failure_code(error: Exception) -> str:
    """Map integrity errors to their envelope code, else IMPORT_FAILED."""
    if isinstance(error, LegacyIntegrityError):
        return error.code
    return "IMPORT_FAILED"


def _success_envelope(
    raw_seen: int, outcome: ImportOutcome, audit_id: str
) -> ResultEnvelope[dict[str, Any]]:
    return ResultEnvelope(
        ok=True,
        data={
            "dry_run": False,
            "raw_records_seen": raw_seen,
            "distinct_candidates": outcome.inserted_candidates,
            "would_import": outcome.inserted_candidates,
            "duplicates": outcome.duplicates,
            "rejected": outcome.rejected,
            "warnings": outcome.warnings,
        },
        audit_id=audit_id,
        next_action="Call radar_list_candidates to review imported records.",
    )


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
        source_run_id = f"run_{uuid.uuid4().hex}"

        path_error = _validate_legacy_path(legacy_path, self.repo_db_path)
        if path_error is not None:
            return path_error

        pre_fingerprint = fingerprint_file(legacy_path)

        transaction = _Transaction(self.db)
        raw_seen = 0
        try:
            filings = read_filings_read_only(legacy_path)
            raw_seen = len(filings)
            if params.dry_run:
                return run_dry_run(
                    filings, self.candidate_repo, legacy_path, pre_fingerprint
                )
            return self._import_filings(
                transaction,
                params,
                filings,
                source_run_id,
                legacy_path,
                pre_fingerprint,
            )
        except Exception as error:
            return self._failure_result(
                error=error,
                code=_failure_code(error),
                params=params,
                source_run_id=source_run_id,
                transaction=transaction,
                raw_seen=raw_seen,
            )

    def _import_filings(
        self,
        transaction: _Transaction,
        params: LegacyImportInput,
        filings: list[dict[str, Any]],
        source_run_id: str,
        legacy_path: Path,
        pre_fingerprint: FileFingerprint,
    ) -> ResultEnvelope[dict[str, Any]]:
        """Run the transactional import and audit its completion."""
        transaction.begin()
        self.source_run_repo.create_run(
            source_run_id=source_run_id,
            source_id="legacy_scout",
            run_type="batch_import",
            params_json=json.dumps(params.model_dump()),
        )
        outcome = persist_import_rows(
            filings,
            raw_repo=self.raw_repo,
            candidate_repo=self.candidate_repo,
            evidence_repo=self.evidence_repo,
            source_run_id=source_run_id,
        )
        self.source_run_repo.complete_run(
            source_run_id=source_run_id,
            records_seen=len(filings),
            records_imported=outcome.inserted_candidates,
            duplicates=outcome.duplicates,
            rejected=outcome.rejected,
        )
        verify_import_snapshot(legacy_path, pre_fingerprint)
        transaction.commit()

        audit_id = self.audit_repo.log_event(
            actor=params.actor,
            action="legacy_import_completed",
            entity_type="source_run",
            entity_id=source_run_id,
            request_data=params.model_dump(),
            result_data={
                "raw_seen": len(filings),
                "inserted_candidates": outcome.inserted_candidates,
                "rejected": outcome.rejected,
                "duplicates": outcome.duplicates,
                "warnings": outcome.warnings,
            },
        )
        return _success_envelope(len(filings), outcome, audit_id)

    def _record_failed_run(
        self,
        source_run_id: str,
        params: LegacyImportInput,
        raw_seen: int,
        error: Exception,
    ) -> None:
        """Re-create the rolled-back run and close it as failed."""
        self.source_run_repo.create_run(
            source_run_id=source_run_id,
            source_id="legacy_scout",
            run_type="batch_import",
            params_json=json.dumps(params.model_dump()),
        )
        self.source_run_repo.complete_run(
            source_run_id=source_run_id,
            records_seen=raw_seen,
            records_imported=0,
            duplicates=0,
            rejected=0,
            error_json=str(error),
        )

    def _failure_result(
        self,
        error: Exception,
        code: str,
        params: LegacyImportInput,
        source_run_id: str,
        transaction: _Transaction,
        raw_seen: int,
    ) -> ResultEnvelope[dict[str, Any]]:
        """Roll back, book a failed source run, audit, and wrap the error."""
        transaction.rollback_if_started()
        if not params.dry_run:
            self._record_failed_run(source_run_id, params, raw_seen, error)
        audit_id = self.audit_repo.log_event(
            actor=params.actor,
            action="legacy_import_failed",
            entity_type="source_run",
            entity_id=source_run_id,
            request_data=params.model_dump(),
            result_data={"error": str(error)},
        )
        return ResultEnvelope(
            ok=False,
            errors=[{"code": code, "message": str(error), "retryable": False}],
            audit_id=audit_id,
        )
