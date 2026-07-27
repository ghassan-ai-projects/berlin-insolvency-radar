"""Unit tests for domain status transitions."""

import pytest

from biradar.domain.statuses import (
    TRANSITION_RULES,
    VALID_STATUSES,
    validate_transition,
)


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


def test_same_status_transition_is_a_valid_noop():
    is_valid, error = validate_transition("needs_review", "needs_review")
    assert is_valid
    assert error is None


def test_target_status_without_a_transition_rule_is_rejected():
    """raw_candidate and deduped_candidate are entry states with no inbound rule."""
    is_valid, error = validate_transition("needs_review", "raw_candidate")
    assert not is_valid
    assert "No transition rule defined" in error


def test_disallowed_source_status_names_the_allowed_set():
    is_valid, error = validate_transition("raw_candidate", "publish_ready")
    assert not is_valid
    assert "review_ready" in error


@pytest.mark.parametrize("status", sorted(VALID_STATUSES))
def test_every_valid_status_is_a_noop_to_itself(status):
    is_valid, _ = validate_transition(status, status)
    assert is_valid


def test_publish_ready_rule_requires_a_score():
    assert TRANSITION_RULES["publish_ready"].requires_score is True


@pytest.mark.parametrize("target", ["rejected", "duplicate", "quarantined"])
def test_negative_outcome_rules_require_a_note(target):
    assert TRANSITION_RULES[target].requires_note is True


def test_all_transition_rule_sources_are_valid_statuses():
    """Guards against a typo in allowed_from silently disabling a transition."""
    for target, rule in TRANSITION_RULES.items():
        assert target in VALID_STATUSES
        for source in rule.allowed_from:
            assert source in VALID_STATUSES, f"{target}.allowed_from has {source!r}"
