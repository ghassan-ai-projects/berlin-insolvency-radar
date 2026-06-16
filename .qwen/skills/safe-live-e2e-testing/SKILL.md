---
name: safe-live-e2e-testing
description: Guidelines for writing cost-conscious, safe live E2E tests for LLM pipelines with dynamic date windows, env loading, and explicit pytest markers.
source: auto-skill
extracted_at: '2026-06-16T10:35:00.000Z'
---

# Safe and Cost-Conscious Live E2E Testing

When validating agentic or LLM-driven pipelines against live external portals and paid/free LLM APIs (e.g., DeepSeek), standard unit testing patterns are insufficient and potentially costly. Use this procedure to write safe, repeatable live E2E tests.

## Core Principles

1. **Explicit Opt-In**: Live tests must never run by default. They should be gated behind a pytest marker (e.g., `@pytest.mark.live`) so standard runs (`pytest -m "not live"`) skip them, preventing accidental API costs or anti-bot IP bans during routine development.
2. **Dynamic Tight Windows**: Never hardcode large historical date ranges. Use a dynamic, minimal window (e.g., `date.today() - timedelta(days=2)`) to minimize LLM token usage and execution time while still validating the real data flow.
3. **Explicit Environment Loading**: Do not assume the test runner has loaded `.env`. Include a helper to explicitly parse and load required API keys (like `DEEPSEEK_API_KEY`) from the project root `.env` file if they are missing from `os.environ`.
4. **Graceful Degradation Assertions**: Assert that the pipeline *completes successfully* even if the live portal legitimately returns 0 records or triggers an anti-bot block (e.g., Cloudflare 403). The goal is to verify the system handles real-world edge cases without crashing, not to guarantee data will be found on any given day.

## Implementation Template

```python
import os
from datetime import date, timedelta
from pathlib import Path
import pytest

def _load_env_from_file():
    """Load environment variables from .env file if not already set."""
    if os.environ.get("REQUIRED_API_KEY"):
        return
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

@pytest.mark.live
def test_pipeline_live_e2e():
    _load_env_from_file()
    assert os.environ.get("REQUIRED_API_KEY"), "API key must be set for live E2E tests"

    # Use a tight, dynamic window to minimize cost and execution time
    today = date.today()
    start_date = today - timedelta(days=2)
    end_date = today

    result = run_pipeline(
        start_date=start_date,
        end_date=end_date,
        dry_run=False,  # Force live execution
        source_mode=None, # Ensure it uses the live adapter, not fixtures
    )

    # Verify the pipeline completed without crashing, even if 0 records were found
    assert result["status"] == "success", f"Pipeline failed: {result.get('error')}"
    
    # Optional: Verify structural integrity of any generated exports
    if result.get("export_path"):
        export_text = Path(result["export_path"]).read_text(encoding="utf-8")
        assert "## Disclaimer" in export_text or "No publish-ready candidates" in export_text
```

## Pytest Configuration

Add the marker to `pyproject.toml` or `pytest.ini` to ensure it is recognized and can be filtered:

```toml
[tool.pytest.ini_options]
markers = [
    "live: marks tests that make live network requests and real API calls (d iselect with '-m \"not live\"')",
]
```