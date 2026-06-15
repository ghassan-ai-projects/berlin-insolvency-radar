"""Unit tests for domain scoring module."""

import pytest

from biradar.domain.scoring import ScoreInput, compute_score


def test_compute_score_hot():
    weights = {
        "company_value": 0.25,
        "asset_quality": 0.20,
        "sector_attractiveness": 0.20,
        "speed_of_action": 0.20,
        "legal_risk": -0.15,
    }
    thresholds = {"hot": 3.0, "solid": 2.5, "interesting": 2.0}

    input_data = ScoreInput(
        company_value=4,
        asset_quality=4,
        sector_attractiveness=4,
        speed_of_action=3,
        legal_risk=2,
    )

    result = compute_score(input_data, weights, thresholds)
    assert result.computed_score == 2.90
    assert result.category == "solid"


def test_compute_score_low_priority():
    weights = {
        "company_value": 0.25,
        "asset_quality": 0.20,
        "sector_attractiveness": 0.20,
        "speed_of_action": 0.20,
        "legal_risk": -0.15,
    }
    thresholds = {"hot": 3.0, "solid": 2.5, "interesting": 2.0}

    input_data = ScoreInput(
        company_value=2,
        asset_quality=2,
        sector_attractiveness=2,
        speed_of_action=2,
        legal_risk=3,
    )

    result = compute_score(input_data, weights, thresholds)
    assert result.computed_score == 1.25
    assert result.category == "low_priority"


def test_score_input_validation():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ScoreInput(
            company_value=6,  # Out of bounds
            asset_quality=2,
            sector_attractiveness=2,
            speed_of_action=2,
            legal_risk=2,
        )
