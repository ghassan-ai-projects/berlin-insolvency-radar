"""Runner entrypoint for the production workflow pipeline."""

from datetime import date
from pathlib import Path
from typing import Any, Literal

from biradar.config.settings import get_settings, load_config
from biradar.observability.logging import get_logger
from biradar.services.pipeline.acquisition import (
    _acquire_raw_records,
    _find_already_processed_raw_ids,
    _record_acquisition_audit,
    _resolve_source_mode,
)
from biradar.services.pipeline.run_steps import (
    _cap_raw_records,
    _compile_workflow,
    _failure_result,
    _invoke_workflow,
    _open_run_databases,
    _persist_stage_outputs,
    _resolve_agent_bindings,
    _skip_stages,
)
from biradar.services.pipeline.stages import (
    _finish_stage,
    _pending_stage_report,
    _portal_only_result,
    _start_stage,
    _success_result,
)
from biradar.sources.enrichment import _reset_disabled_sources

logger = get_logger(__name__)

RunMode = Literal["full_live", "portal_only", "portal_with_stubs"]


def run_pipeline(
    start_date: date,
    end_date: date,
    dry_run: bool = False,
    thread_id: str = "pipeline_default",
    db_path: str | Path | None = None,
    source_mode: str | None = None,
    extractor: Any | None = None,
    risk_reviewer: Any | None = None,
    enricher: Any | None = None,
    max_records: int | None = None,
    run_mode: RunMode = "full_live",
) -> dict[str, Any]:
    """Execute the agentic workflow pipeline."""
    logger.info(
        "Starting pipeline execution",
        extra={
            "start_date": str(start_date),
            "end_date": str(end_date),
            "dry_run": dry_run,
        },
    )

    settings = get_settings()
    config = load_config(settings.project_root / "config")
    resolved_extractor, resolved_risk_reviewer, resolved_enricher = (
        _resolve_agent_bindings(extractor, risk_reviewer, enricher, run_mode)
    )
    stage_report = _pending_stage_report()
    official_source_cfg = config.sources.get("official_insolvency_berlin")
    effective_source_mode = _resolve_source_mode(source_mode, official_source_cfg)
    db, checkpoint_mgr = _open_run_databases(settings, db_path, dry_run)

    try:
        fetch_started_at = _start_stage(stage_report, "fetch")
        acquired = _acquire_raw_records(
            db=db,
            settings=settings,
            config=config,
            start_date=start_date,
            end_date=end_date,
            dry_run=dry_run,
            effective_source_mode=effective_source_mode,
            stage_report=stage_report,
            fetch_started_at=fetch_started_at,
        )
        if isinstance(acquired, dict):
            return acquired
        source_run_id, raw_records = acquired

        _finish_stage(
            stage_report,
            "fetch",
            fetch_started_at,
            "success",
            record_count=len(raw_records),
            source_run_id=source_run_id,
        )
        if not dry_run:
            _record_acquisition_audit(
                db,
                source_run_id,
                start_date,
                end_date,
                effective_source_mode,
                run_mode,
                len(raw_records),
            )

        _reset_disabled_sources()

        workflow = _compile_workflow(
            resolved_extractor,
            resolved_risk_reviewer,
            resolved_enricher,
            checkpoint_mgr,
        )
        already_processed_ids = (
            [] if dry_run else _find_already_processed_raw_ids(db, raw_records)
        )
        raw_records = _cap_raw_records(raw_records, max_records)

        if run_mode == "portal_only":
            _skip_stages(stage_report, ["workflow", "persist"], "run_mode=portal_only")
            return _portal_only_result(stage_report)

        final_state = _invoke_workflow(
            workflow,
            source_run_id,
            raw_records,
            already_processed_ids,
            thread_id,
            start_date,
            end_date,
            dry_run,
            stage_report,
        )
        issue_id = _persist_stage_outputs(db, final_state, stage_report, dry_run)

        logger.info("Pipeline completed successfully")
        return _success_result(final_state, issue_id, stage_report)
    except Exception as exc:
        return _failure_result(stage_report, exc)
    finally:
        checkpoint_mgr.close()
        db.close()
