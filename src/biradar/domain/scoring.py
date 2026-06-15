"""Deterministic opportunity scoring engine."""

from pydantic import BaseModel, Field


class ScoreInput(BaseModel):
    company_value: int = Field(ge=1, le=5)
    asset_quality: int = Field(ge=1, le=5)
    sector_attractiveness: int = Field(ge=1, le=5)
    speed_of_action: int = Field(ge=1, le=5)
    legal_risk: int = Field(ge=1, le=5)
    rationale: dict[str, str] = Field(default_factory=dict)


class ScoreResult(BaseModel):
    computed_score: float
    category: str


def compute_score(
    input_data: ScoreInput, weights: dict[str, float], thresholds: dict[str, float]
) -> ScoreResult:
    """
    Compute the editorial opportunity score deterministically.

    Formula: (A * w_A) + (B * w_B) + (C * w_C) + (D * w_D) - (E * w_E)
    Note: legal_risk weight should be negative in config, so we add it directly.
    """
    score = (
        (input_data.company_value * weights["company_value"])
        + (input_data.asset_quality * weights["asset_quality"])
        + (input_data.sector_attractiveness * weights["sector_attractiveness"])
        + (input_data.speed_of_action * weights["speed_of_action"])
        + (input_data.legal_risk * weights["legal_risk"])  # Weight is negative
    )

    # Round to 2 decimal places
    computed_score = round(score, 2)

    # Determine category
    if computed_score >= thresholds.get("hot", 3.0):
        category = "hot"
    elif computed_score >= thresholds.get("solid", 2.5):
        category = "solid"
    elif computed_score >= thresholds.get("interesting", 2.0):
        category = "interesting"
    else:
        category = "low_priority"

    return ScoreResult(computed_score=computed_score, category=category)
