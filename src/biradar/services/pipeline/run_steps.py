"""Per-run helper steps for the pipeline runner: setup, invocation, outcomes."""

# pyright: reportArgumentType=false
#
# Scoped to this module for LangGraph's RunnableConfig, which is typed too
# narrowly upstream to accept the plain `{"configurable": {...}}` dict its own
# documentation prescribes.

from datetime import date
from pathlib import Path
from typing import Any

from biradar.graph.checkpoints import CheckpointManager
from biradar.graph.pipeline_workflow import build_pipeline_workflow
from biradar.graph.state import build_initial_pipeline_state
from biradar.observability.logging import get_logger
from biradar.services.pipeline.persistence import _persist_results
from biradar.services.pipeline.stages import _finish_stage, _start_stage
from biradar.services.pipeline.stubs import (
    _stub_enricher,
    _stub_extractor,
    _stub_risk_reviewer,
)
from biradar.storage.db import Database

logger = get_logger(__name__)


def _resolve_agent_bindings(
    extractor: Any | None,
    risk_reviewer: Any | None,
    enricher: Any | None,
    run_mode: str,
) -> tuple[Any | None, Any | None, Any | None]:
    """Fall back to deterministic stubs when the run mode asks for them."""
    if run_mode != "portal_with_stubs":
        return extractor, risk_reviewer, enricher
    return (
        extractor or _stub_extractor,
        risk_reviewer or _stub_risk_reviewer,
        enricher or _stub_enricher,
    )


def _open_run_databases(
    settings: Any, db_path: str | Path | None, dry_run: bool
) -> tuple[Database, CheckpointManager]:
    """Open (and migrate) the radar database and its checkpoint store.

    Dry runs use in-memory databases on purpose: nothing may persist.
    """
    if dry_run:
        db = Database(":memory:")
        checkpoint_db_path: str | Path = ":memory:"
    else:
        db = Database(_resolve_db_path(settings, db_path))
        checkpoint_db_path = settings.data_dir / "checkpoints.sqlite"
    db.run_migrations()
    return db, CheckpointManager(checkpoint_db_path)


def _resolve_db_path(settings: Any, db_path: str | Path | None) -> Path:
    return Path(db_path) if db_path else settings.data_dir / "radar.duckdb"


def _compile_workflow(
    extractor: Any | None,
    risk_reviewer: Any | None,
    enricher: Any | None,
    checkpoint_mgr: CheckpointManager,
) -> Any:
    return build_pipeline_workflow(
        extractor=extractor,
        risk_reviewer=risk_reviewer,
        enricher=enricher,
    ).compile(checkpointer=checkpoint_mgr.saver_instance)


def _cap_raw_records(
    raw_records: list[dict[str, Any]], max_records: int | None
) -> list[dict[str, Any]]:
    """Cap the record count for quick validation runs."""
    if max_records is not None and len(raw_records) > max_records:
        logger.info(f"Capping raw records from {len(raw_records)} to {max_records}")
        return raw_records[:max_records]
    return raw_records


def _skip_stages(
    stage_report: dict[str, dict[str, Any]], names: list[str], reason: str
) -> None:
    for name in names:
        stage_report[name] = {"status": "skipped", "reason": reason}


def _invoke_workflow(
    workflow: Any,
    source_run_id: str,
    raw_records: list[dict[str, Any]],
    already_processed_ids: list[str],
    thread_id: str,
    start_date: date,
    end_date: date,
    dry_run: bool,
    stage_report: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Run the compiled workflow and record the stage outcome."""
    initial_state = build_initial_pipeline_state(
        source_run_id=source_run_id,
        raw_records=raw_records,
        already_processed_raw_ids=already_processed_ids,
    )
    invocation_config = {
        "configurable": {
            "thread_id": thread_id,
            "start_date": start_date,
            "end_date": end_date,
            "dry_run": dry_run,
        }
    }
    workflow_started_at = _start_stage(stage_report, "workflow")
    final_state = workflow.invoke(initial_state, invocation_config)
    workflow_status = "failed" if final_state.get("errors") else "success"
    _finish_stage(
        stage_report,
        "workflow",
        workflow_started_at,
        workflow_status,
        current_step=final_state.get("current_step"),
        warning_count=len(final_state.get("warnings", [])),
        error_count=len(final_state.get("errors", [])),
    )
    return final_state


def _persist_stage_outputs(
    db: Database,
    final_state: dict[str, Any],
    stage_report: dict[str, dict[str, Any]],
    dry_run: bool,
) -> str | None:
    """Persist workflow outputs unless this is a dry run."""
    if dry_run:
        stage_report["persist"] = {
            "status": "skipped",
            "reason": "dry_run=True",
        }
        return None
    persist_started_at = _start_stage(stage_report, "persist")
    issue_id = _persist_results(db, final_state, final_state.get("export_path"))
    _finish_stage(
        stage_report,
        "persist",
        persist_started_at,
        "success",
        issue_id=issue_id,
    )
    return issue_id


def _failure_result(
    stage_report: dict[str, dict[str, Any]], exc: Exception
) -> dict[str, Any]:
    logger.error("Pipeline failed", exc_info=True)
    stage_report["workflow"] = {
        **stage_report.get("workflow", {}),
        "status": "failed",
        "error": str(exc),
    }
    return {
        "status": "failed",
        "error": str(exc),
        "stage_report": stage_report,
    }
