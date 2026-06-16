"""Typed configuration loading for the application."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


class Settings(BaseModel):
    """Application runtime settings."""
    project_root: Path = Field(default=Path(os.getcwd()))
    
    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"


def get_settings() -> Settings:
    return Settings()


class ScoringConfig(BaseModel):
    version: str
    weights: dict[str, float]
    thresholds: dict[str, float]

    @model_validator(mode="after")
    def check_weights(self) -> "ScoringConfig":
        expected_keys = {
            "company_value",
            "asset_quality",
            "sector_attractiveness",
            "speed_of_action",
            "legal_risk",
        }
        if set(self.weights.keys()) != expected_keys:
            raise ValueError(f"Scoring weights must contain exactly: {expected_keys}")
        return self


class SourceConfig(BaseModel):
    kind: str
    name: str
    enabled: bool
    trust_level: str
    params: dict[str, Any] = Field(default_factory=dict)
    mode: str = Field(default="normal")
    path: str | None = None


class AppConfig(BaseModel):
    scoring: ScoringConfig
    sources: dict[str, SourceConfig]


def load_config(config_dir: Path | str) -> AppConfig:
    """Load and validate application configuration from YAML files."""
    config_path = Path(config_dir)

    scoring_path = config_path / "scoring.yaml"
    sources_path = config_path / "sources.yaml"

    if not scoring_path.exists():
        raise FileNotFoundError(f"Scoring config not found at {scoring_path}")
    if not sources_path.exists():
        raise FileNotFoundError(f"Sources config not found at {sources_path}")

    with open(scoring_path) as f:
        scoring_data = yaml.safe_load(f)

    with open(sources_path) as f:
        sources_data = yaml.safe_load(f)

    scoring = ScoringConfig(**scoring_data)
    sources = {
        name: SourceConfig(**data)
        for name, data in sources_data.get("sources", {}).items()
    }

    return AppConfig(scoring=scoring, sources=sources)
