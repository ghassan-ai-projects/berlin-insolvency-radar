"""Service entrypoints for the production workflow pipeline.

The pipeline lives in per-concern modules inside this package and is
re-exported here, so ``biradar.services.pipeline`` stays the single import
surface for the CLI, the MCP server, and the E2E tests.
"""

from biradar.services.pipeline.runner import RunMode, run_pipeline
from biradar.services.pipeline.selfcheck import run_pipeline_check
from biradar.services.pipeline.stubs import (
    _stub_enricher,
    _stub_extractor,
    _stub_risk_reviewer,
)

__all__ = [
    "RunMode",
    "_stub_enricher",
    "_stub_extractor",
    "_stub_risk_reviewer",
    "run_pipeline",
    "run_pipeline_check",
]
