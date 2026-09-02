"""Source acquisition for pipeline runs: fixtures, live portal, and caching."""

from asyncio import run as asyncio_run
from pathlib import Path
from typing import Any

from biradar.config.settings import AppConfig, Settings
from biradar.observability.logging import get_logger
from biradar.services.pipeline.stages import _fail_result
from biradar.services.pipeline.stubs import _load_fixture_records
from biradar.sources.official_portal import OfficialPortalAdapter
from biradar.storage.db import Database
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    RawRecordRepository,
    SourceRunRepository,
)

logger = get_logger(__name__)


def _resolve_source_mode(source_mode: str | None, official_source_cfg: Any) -> str:
    """Prefer an explicit source mode; otherwise take the configured one."""
    return source_mode or (
        official_source_cfg.mode if official_source_cfg else "normal"
    )


def _acquire_raw_records(
    db: Database,
    settings: Settings,
    config: AppConfig,
    start_date: Any,
    end_date: Any,
    dry_run: bool,
    effective_source_mode: str,
    stage_report: dict[str, dict[str, Any]],
    fetch_started_at: float,
) -> tuple[str, list[dict[str, Any]]] | dict[str, Any]:
    """Fetch the raw records for a run, or return the failure result on error.

    A successful acquisition yields ``(source_run_id, raw_records)``; a failed
    one yields the ready-to-return failure result dict.
    """
    if dry_run:
        return _load_fixture_records(settings)
    if effective_source_mode == "fixture":
        return _fetch_from_fixture(
            db, settings, config, start_date, end_date, stage_report, fetch_started_at
        )
    return _fetch_live_with_cache(
        db, start_date, end_date, stage_report, fetch_started_at
    )


def _fetch_from_fixture(
    db: Database,
    settings: Settings,
    config: AppConfig,
    start_date: Any,
    end_date: Any,
    stage_report: dict[str, dict[str, Any]],
    fetch_started_at: float,
) -> tuple[str, list[dict[str, Any]]] | dict[str, Any]:
    """Run acquisition against a local fixture file instead of the live portal."""
    fetch_result = OfficialPortalAdapter(db).fetch_fixture_date_range(
        fixture_path=str(_resolve_fixture_path(settings, config)),
        start_date=start_date,
        end_date=end_date,
        dry_run=False,
    )
    if fetch_result["status"] != "completed":
        return _fail_fetch(
            stage_report,
            fetch_started_at,
            "Official portal fixture acquisition failed",
            fetch_result,
        )
    return fetch_result["source_run_id"], fetch_result.get("records", [])


def _resolve_fixture_path(settings: Settings, config: AppConfig) -> Path:
    """Prefer the configured fixture file; fall back to the repo sample."""
    official_source_cfg = config.sources.get("official_insolvency_berlin")
    if official_source_cfg and official_source_cfg.path:
        return Path(official_source_cfg.path)
    return (
        settings.project_root
        / "tests"
        / "fixtures"
        / "official_portal"
        / "sample_response.html"
    )


def _fetch_live_with_cache(
    db: Database,
    start_date: Any,
    end_date: Any,
    stage_report: dict[str, dict[str, Any]],
    fetch_started_at: float,
) -> tuple[str, list[dict[str, Any]]] | dict[str, Any]:
    """Reuse a completed run covering the window when possible, else fetch live."""
    source_id = "official_insolvency_berlin"
    covering_run_id = SourceRunRepository(db).find_covering_run(
        source_id,
        start_date.isoformat(),
        end_date.isoformat(),
    )
    if covering_run_id:
        cached_records = RawRecordRepository(db).list_by_source_run(covering_run_id)
        if cached_records:
            return covering_run_id, cached_records
    return _fetch_live(db, start_date, end_date, stage_report, fetch_started_at)


def _fetch_live(
    db: Database,
    start_date: Any,
    end_date: Any,
    stage_report: dict[str, dict[str, Any]],
    fetch_started_at: float,
) -> tuple[str, list[dict[str, Any]]] | dict[str, Any]:
    """Fetch the requested date window from the live official portal."""
    fetch_result = asyncio_run(
        OfficialPortalAdapter(db).fetch_date_range(
            start_date=start_date,
            end_date=end_date,
            dry_run=False,
        )
    )
    if fetch_result["status"] != "completed":
        return _fail_fetch(
            stage_report,
            fetch_started_at,
            "Official portal acquisition failed",
            fetch_result,
        )
    return fetch_result["source_run_id"], fetch_result.get("records", [])


def _fail_fetch(
    stage_report: dict[str, dict[str, Any]],
    fetch_started_at: float,
    message: str,
    fetch_result: dict[str, Any],
) -> dict[str, Any]:
    """Turn a failed portal fetch into the pipeline failure result."""
    return _fail_result(
        stage_report,
        "fetch",
        fetch_started_at,
        message,
        fetch_result.get("errors", []),
    )


def _record_acquisition_audit(
    db: Database,
    source_run_id: str,
    start_date: Any,
    end_date: Any,
    effective_source_mode: str,
    run_mode: str,
    record_count: int,
) -> None:
    """Log the completed acquisition to the audit trail."""
    AuditRepository(db).log_event(
        actor="system:pipeline",
        action="pipeline_acquisition_completed",
        entity_type="source_run",
        entity_id=source_run_id,
        request_data={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "source_mode": effective_source_mode,
            "run_mode": run_mode,
        },
        result_data={"raw_records": record_count},
    )


def _find_already_processed_raw_ids(
    db: Database, raw_records: list[dict[str, Any]]
) -> list[str]:
    """Collect raw_record_ids that already have candidates (skip re-extraction)."""
    raw_ids: list[str] = []
    for record in raw_records:
        raw_id = record.get("raw_record_id")
        if raw_id:
            raw_ids.append(raw_id)
    if not raw_ids:
        return []
    return CandidateRepository(db).find_raw_ids_with_candidates(raw_ids)
