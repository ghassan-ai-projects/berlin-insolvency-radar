"""Unit tests for domain status transitions."""

from biradar.domain.statuses import validate_transition


def test_valid_transitions():
    is_valid, msg = validate_transition("raw_candidate", "needs_review")
    assert is_valid is True
    assert msg is None

    is_valid, msg = validate_transition("review_ready", "publish_ready")
    assert is_valid is True
    assert msg is None


def test_invalid_transitions():
    is_valid, msg = validate_transition("quarantined", "publish_ready")
    assert is_valid is False
    assert "Cannot transition" in msg

    is_valid, msg = validate_transition("raw_candidate", "publish_ready")
    assert is_valid is False
    assert "Cannot transition" in msg


def test_invalid_statuses():
    is_valid, msg = validate_transition("invalid_status", "needs_review")
    assert is_valid is False
    assert "Invalid current status" in msg
