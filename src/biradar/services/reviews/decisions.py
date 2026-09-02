"""Decision vocabulary for candidate reviews."""

ALLOWED_DECISIONS = {
    "approve",
    "reject",
    "needs_more_info",
    "mark_duplicate",
    "archive",
}

DECISION_TARGET_STATUS = {
    "approve": "publish_ready",
    "reject": "rejected",
    "needs_more_info": "needs_review",
    "mark_duplicate": "duplicate",
    "archive": "archived",
}
