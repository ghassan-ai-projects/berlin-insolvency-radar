"""Audit-and-fail outcome construction for candidate reviews."""

from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.repository import AuditRepository


def _review_failure(
    audit_repo: AuditRepository,
    *,
    reviewer: str,
    candidate_id: str,
    decision: str,
    score_input: dict[str, Any] | None,
    error: str | None,
    code: str,
    message: str | None,
) -> ResultEnvelope[dict[str, Any]]:
    """Audit the rejected review attempt and return its failure envelope."""
    audit_id = audit_repo.log_event(
        actor=reviewer,
        action="candidate_review_failed",
        entity_type="candidate",
        entity_id=candidate_id,
        request_data={"decision": decision, "score_input": score_input},
        result_data={"error": error},
    )
    return ResultEnvelope(
        ok=False,
        errors=[{"code": code, "message": message, "retryable": False}],
        audit_id=audit_id,
    )
