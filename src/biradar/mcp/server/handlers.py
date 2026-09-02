"""Radar tool handlers: thin adapters from tool params to services."""

from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.mcp.schemas import (
    AuditTrailInput,
    CreateIssueDraftInput,
    ExportIssueInput,
    GetCandidateInput,
    HealthInput,
    ImportLegacyScoutInput,
    ListCandidatesInput,
    ListSourceRunsInput,
    ReviewCandidateInput,
    RunWorkflowInput,
)
from biradar.services.container import AppContainer
from biradar.services.pipeline import run_pipeline


def _workflow_result_to_envelope(result: dict[str, Any]) -> ResultEnvelope[Any]:
    return ResultEnvelope(
        ok=result.get("status") == "success",
        data=result,
        errors=(
            []
            if result.get("status") == "success"
            else [
                {
                    "code": "WORKFLOW_FAILED",
                    "message": result.get("error", "Workflow failed."),
                    "retryable": True,
                }
            ]
        ),
        next_action=(
            "Inspect radar_audit_trail and exported artifacts."
            if result.get("status") == "success"
            else "Review the workflow error and retry the run."
        ),
    )


def _check_health(container: AppContainer, _params: HealthInput) -> ResultEnvelope[Any]:
    return container.health.check()


def _import_legacy_scout(
    container: AppContainer, params: ImportLegacyScoutInput
) -> ResultEnvelope[Any]:
    return container.legacy_import.import_legacy_scout(params)


def _list_candidates(
    container: AppContainer, params: ListCandidatesInput
) -> ResultEnvelope[Any]:
    return container.candidates.list_candidates(
        statuses=list(params.statuses) if params.statuses else None,
        limit=params.limit,
        offset=params.offset,
    )


def _get_candidate(
    container: AppContainer, params: GetCandidateInput
) -> ResultEnvelope[Any]:
    return container.candidates.get_candidate(params.candidate_id)


def _review_candidate(
    container: AppContainer, params: ReviewCandidateInput
) -> ResultEnvelope[Any]:
    return container.reviews.review_candidate(
        candidate_id=params.candidate_id,
        decision=params.decision,
        reviewer=params.reviewer,
        note=params.note,
        score_input=(params.score_input.model_dump() if params.score_input else None),
    )


def _create_issue_draft(
    container: AppContainer, params: CreateIssueDraftInput
) -> ResultEnvelope[Any]:
    return container.issues.create_issue_draft(
        week=params.week,
        tier=params.tier,
        candidate_ids=params.candidate_ids,
        title=params.title,
        include_disclaimer=params.include_disclaimer,
        actor=params.actor,
    )


def _export_issue(
    container: AppContainer, params: ExportIssueInput
) -> ResultEnvelope[Any]:
    return container.issues.export_issue(
        issue_id=params.issue_id,
        format=params.format,
        actor=params.actor,
    )


def _audit_trail(
    container: AppContainer, params: AuditTrailInput
) -> ResultEnvelope[Any]:
    return _ok_envelope(
        container.audit_repo.get_events(
            entity_type=params.entity_type,
            entity_id=params.entity_id,
            actor=params.actor,
            limit=params.limit,
        )
    )


def _list_source_runs(
    container: AppContainer, params: ListSourceRunsInput
) -> ResultEnvelope[Any]:
    return _ok_envelope(
        container.health.source_repo.list_runs(
            source_id=params.source_id,
            status=params.status,
            limit=params.limit,
        )
    )


def _run_workflow(
    _container: AppContainer, params: RunWorkflowInput
) -> ResultEnvelope[Any]:
    return _workflow_result_to_envelope(
        run_pipeline(
            start_date=params.start_date,
            end_date=params.end_date,
            dry_run=params.dry_run,
        )
    )


def _ok_envelope(data: Any) -> ResultEnvelope[Any]:
    """Wrap raw repository data in a bare success envelope."""
    return ResultEnvelope(ok=True, data=data)
