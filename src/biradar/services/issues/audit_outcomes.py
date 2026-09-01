"""Audit-and-fail outcome construction for the issue service."""

from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.repository import AuditRepository


def _failure_envelope(
    audit_repo: AuditRepository,
    *,
    actor: str,
    action: str,
    entity_id: str,
    request_data: dict[str, Any],
    result_data: dict[str, Any],
    code: str,
    message: str,
    warnings: list[str] | None = None,
) -> ResultEnvelope[dict[str, Any]]:
    """Log the failure audit event and wrap it in a failure envelope."""
    audit_id = audit_repo.log_event(
        actor=actor,
        action=action,
        entity_type="issue",
        entity_id=entity_id,
        request_data=request_data,
        result_data=result_data,
    )
    return ResultEnvelope(
        ok=False,
        warnings=warnings or [],
        errors=[{"code": code, "message": message, "retryable": False}],
        audit_id=audit_id,
    )
