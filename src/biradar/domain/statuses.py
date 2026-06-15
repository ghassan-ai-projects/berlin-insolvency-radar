"""State machine validation for candidate status transitions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StatusTransitionRule:
    allowed_from: list[str]
    requires_note: bool
    requires_score: bool


VALID_STATUSES = {
    "raw_candidate",
    "deduped_candidate",
    "needs_review",
    "review_ready",
    "publish_ready",
    "rejected",
    "archived",
    "duplicate",
    "quarantined",
}

# Define allowed transitions
TRANSITION_RULES: dict[str, StatusTransitionRule] = {
    "needs_review": StatusTransitionRule(
        allowed_from=["raw_candidate", "deduped_candidate", "review_ready"],
        requires_note=False,
        requires_score=False,
    ),
    "review_ready": StatusTransitionRule(
        allowed_from=["needs_review"],
        requires_note=False,
        requires_score=False,
    ),
    "publish_ready": StatusTransitionRule(
        allowed_from=["review_ready"],
        requires_note=False,
        requires_score=True,
    ),
    "rejected": StatusTransitionRule(
        allowed_from=["raw_candidate", "needs_review", "review_ready"],
        requires_note=True,
        requires_score=False,
    ),
    "archived": StatusTransitionRule(
        allowed_from=["rejected", "duplicate", "quarantined", "publish_ready"],
        requires_note=False,
        requires_score=False,
    ),
    "duplicate": StatusTransitionRule(
        allowed_from=[
            "raw_candidate",
            "deduped_candidate",
            "needs_review",
            "review_ready",
        ],
        requires_note=True,
        requires_score=False,
    ),
    "quarantined": StatusTransitionRule(
        allowed_from=["raw_candidate"],
        requires_note=True,
        requires_score=False,
    ),
}


def validate_transition(
    current_status: str, target_status: str
) -> tuple[bool, str | None]:
    """
    Validate a candidate status transition.

    Returns:
        (is_valid, error_message_if_invalid)
    """
    if current_status not in VALID_STATUSES:
        return False, f"Invalid current status: {current_status}"
    if target_status not in VALID_STATUSES:
        return False, f"Invalid target status: {target_status}"
    if current_status == target_status:
        return True, None  # No-op is valid

    rule = TRANSITION_RULES.get(target_status)
    if not rule:
        return False, f"No transition rule defined for target status: {target_status}"

    if current_status not in rule.allowed_from:
        return (
            False,
            f"Cannot transition from '{current_status}' to '{target_status}'. Allowed from: {rule.allowed_from}",
        )

    return True, None
