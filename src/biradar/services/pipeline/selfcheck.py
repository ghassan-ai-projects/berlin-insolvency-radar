"""Self-verification entrypoint: two fixture-backed runs against a temp database."""

import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from biradar.services.pipeline.runner import run_pipeline
from biradar.services.pipeline.stubs import (
    _stub_enricher,
    _stub_extractor,
    _stub_risk_reviewer,
)
from biradar.storage.db import Database, scalar_count


def run_pipeline_check() -> dict[str, Any]:
    """Run a full local verification pass against fixture-backed acquisition and deterministic stubs."""
    start_date = date(2026, 6, 10)
    end_date = date(2026, 6, 16)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "pipeline_check.duckdb"
        first = _run_check_pass(db_path, start_date, end_date, "pipeline_check_first")
        second = _run_check_pass(db_path, start_date, end_date, "pipeline_check_second")
        counts = _count_verification_rows(db_path)
        return {
            "status": "success"
            if first["status"] == "success" and second["status"] == "success"
            else "failed",
            "first_run": first,
            "second_run": second,
            "counts": counts,
        }


def _run_check_pass(
    db_path: Path, start_date: date, end_date: date, thread_id: str
) -> dict[str, Any]:
    return run_pipeline(
        start_date=start_date,
        end_date=end_date,
        dry_run=False,
        thread_id=thread_id,
        db_path=db_path,
        source_mode="fixture",
        extractor=_stub_extractor,
        risk_reviewer=_stub_risk_reviewer,
        enricher=_stub_enricher,
    )


def _count_verification_rows(db_path: Path) -> dict[str, int]:
    db = Database(db_path)
    try:
        return {
            "source_runs": scalar_count(db.conn, "SELECT COUNT(*) FROM source_runs"),
            "raw_records": scalar_count(db.conn, "SELECT COUNT(*) FROM raw_records"),
            "candidates": scalar_count(db.conn, "SELECT COUNT(*) FROM candidates"),
            "publish_ready": scalar_count(
                db.conn,
                "SELECT COUNT(*) FROM candidates WHERE status = 'publish_ready'",
            ),
            "issues": scalar_count(db.conn, "SELECT COUNT(*) FROM issues"),
        }
    finally:
        db.close()
