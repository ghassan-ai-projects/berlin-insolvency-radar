"""Unit tests for typed configuration loading."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from biradar.config.settings import (
    EnrichmentConfig,
    ScoringConfig,
    get_settings,
    load_config,
)


def _write_minimal_configs(
    config_dir: Path, *, scoring: str | None = None, sources: str | None = None
) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    if scoring is not None:
        (config_dir / "scoring.yaml").write_text(scoring, encoding="utf-8")
    if sources is not None:
        (config_dir / "sources.yaml").write_text(sources, encoding="utf-8")


VALID_SCORING = """
version: test-1.0.0
weights:
  company_value: 0.3
  asset_quality: 0.2
  sector_attractiveness: 0.2
  speed_of_action: 0.2
  legal_risk: 0.1
thresholds:
  hot: 80
"""

VALID_SOURCES = """
sources:
  official_portal:
    kind: portal
    name: Official Portal
    enabled: true
    trust_level: official
enrichment:
  enabled: false
  sources:
    github: true
    wikidata:
      enabled: false
      timeout_seconds: 2.5
"""


def test_get_settings_defaults_project_root_to_the_repo_root():
    settings = get_settings()

    assert settings.project_root.name == "berlin-insolvency-radar"
    assert settings.data_dir.name == "data"


def test_load_config_reads_scoring_sources_and_enrichment(tmp_path):
    _write_minimal_configs(tmp_path, scoring=VALID_SCORING, sources=VALID_SOURCES)

    config = load_config(tmp_path)

    assert config.scoring.version == "test-1.0.0"
    assert config.sources["official_portal"].trust_level == "official"
    assert config.enrichment.sources["github"].enabled is True
    assert config.enrichment.sources["wikidata"].timeout_seconds == 2.5


def test_load_config_rejects_scoring_weights_with_missing_dimensions(tmp_path):
    bad_scoring = VALID_SCORING.replace("  legal_risk: 0.1\n", "")
    _write_minimal_configs(tmp_path, scoring=bad_scoring, sources=VALID_SOURCES)

    with pytest.raises(ValidationError, match="exactly"):
        load_config(tmp_path)


def test_load_config_raises_when_scoring_yaml_is_missing(tmp_path):
    _write_minimal_configs(tmp_path, sources=VALID_SOURCES)

    with pytest.raises(FileNotFoundError, match="Scoring config"):
        load_config(tmp_path)


def test_load_config_raises_when_sources_yaml_is_missing(tmp_path):
    _write_minimal_configs(tmp_path, scoring=VALID_SCORING)

    with pytest.raises(FileNotFoundError, match="Sources config"):
        load_config(tmp_path)


def test_enrichment_sources_accept_bool_shortcuts_and_none():
    config = EnrichmentConfig(sources={"github": True, "wikidata": False})

    assert config.sources["github"].enabled is True
    assert config.sources["wikidata"].enabled is False


def test_enrichment_sources_default_to_empty_when_omitted():
    assert EnrichmentConfig(sources=None).sources == {}
    assert EnrichmentConfig().sources == {}


def test_enrichment_sources_reject_non_bool_non_mapping_values():
    with pytest.raises(TypeError, match="bool or mapping"):
        EnrichmentConfig(sources={"github": "yes"})


def test_scoring_config_rejects_extra_weight_dimensions():
    with pytest.raises(ValidationError, match="exactly"):
        ScoringConfig(
            version="bad",
            weights={"company_value": 1.0, "mystery": 1.0},
            thresholds={},
        )
