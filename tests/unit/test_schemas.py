"""Unit tests for MCP input schema validation."""

import pytest
from pydantic import ValidationError

from biradar.mcp.schemas import CreateIssueDraftInput


def _draft(week: str) -> CreateIssueDraftInput:
    return CreateIssueDraftInput(
        week=week, tier="free", candidate_ids=["cand_1"], title="Issue"
    )


@pytest.mark.parametrize("week", ["2026-W01", "2026-W25", "2026-W53", "2025-W52"])
def test_create_issue_draft_accepts_valid_iso_weeks(week):
    assert _draft(week).week == week


@pytest.mark.parametrize("week", ["2026-W00", "2026-W99", "2026-W54"])
def test_create_issue_draft_rejects_out_of_range_weeks(week):
    with pytest.raises(ValidationError):
        _draft(week)


@pytest.mark.parametrize("week", ["2025-W53", "2021-W53", "2024-W53"])
def test_create_issue_draft_rejects_week_53_in_short_iso_years(week):
    """Week 53 exists only in long ISO years, so it cannot be range-checked alone."""
    with pytest.raises(ValidationError):
        _draft(week)


@pytest.mark.parametrize("week", ["2026-25", "26-W25", "2026-W5", "week25", ""])
def test_create_issue_draft_rejects_malformed_week_strings(week):
    with pytest.raises(ValidationError):
        _draft(week)


def test_create_issue_draft_week_error_names_the_bad_value():
    with pytest.raises(ValidationError, match="2026-W00"):
        _draft("2026-W00")
