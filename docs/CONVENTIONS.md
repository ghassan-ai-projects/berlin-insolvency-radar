# Conventions — Berlin Insolvency Radar

## Overview
This project is an AI-powered insolvency intelligence radar for Berlin. It scrapes the official
insolvency portal, extracts structured facts via LLM, enriches with public sources, scores
opportunities deterministically, and exports Markdown newsletter drafts.

## Architecture

```
Layer 5 (Entry):     cli/main  ,  mcp/server
Layer 4 (Orch):      services/phase2_pipeline  ,  services/container (DI)
Layer 3 (Logic):     graph/  ,  services/{health,candidates,issues,reviews,import_legacy}
Layer 2 (Adapters):  agents/  ,  domain/  ,  output/  ,  sources/
Layer 1 (Infra):     config/  ,  observability/  ,  storage/{db,repository}
```

- Dependencies flow top-down only. No circular imports.
- `domain/` modules are pure functions with zero I/O and zero side effects.
- All SQL lives in `storage/repository.py`. No raw SQL outside `storage/`.
- All services return `ResultEnvelope[T]` from `mcp/envelope.py`.
- DI via `AppContainer` (see `services/container.py`). Entry points compose from this root.

## Code Style

- **Logging:** Use `logging.getLogger(__name__)` (or `from biradar.observability.logging import get_logger`).
- **Typing:** All function signatures are typed. Use `dict[str, Any]` for untyped dicts, Pydantic for structured data.
- **IDs:** UUID prefixes follow a convention: `run_`, `cand_`, `raw_`, `ev_`, `score_`, `rev_`, `issue_`, `audit_`.
- **State mutation in LangGraph nodes:** Always return a shallow copy `{**state}` rather than the mutated reference.
- **Error handling:** Services return `ResultEnvelope(ok=False, errors=[...])` — never raise exceptions across MCP boundaries. The catch-all in `mcp/server.py` returns a generic message; log details server-side.
- **LLM calls:** Always use explicit `model_kwargs={"response_format": {"type": "json_object"}}` for DeepSeek. Wrap injected data in XML delimiters (`<raw_notice>`, `<candidate_data>`, etc.) with instructions to treat data as data.

## Tests

- `tests/unit/` — Fast, no I/O. Mock LLM agents.
- `tests/acceptance/` — Phase gating tests. Real DuckDB.
- `tests/e2e/` — Full pipeline. `@pytest.mark.live` gates live portal tests.
- `conftest.py` defaults `BI_RADAR_USE_MOCK_AGENTS=1` for safety.
- Run: `make test` (unit), `make test-acceptance`, `make test-e2e`, `make check` (all).

## Secrets

- `DEEPSEEK_API_KEY` from environment only. `.env` is gitignored.
- `.env.example` documents required variables. Never commit real keys.
- Data directory (`data/`) is gitignored — checkpoint states, databases, exports.

## Config

- `config/scoring.yaml` — scoring weights and thresholds.
- `config/sources.yaml` — source adapter modes and parameters.
- `config/settings.py` — `Settings` (project root, data dir) and `AppConfig` (scoring + sources).

## PR Checklist

- [ ] All tests pass (`make check`)
- [ ] No raw API keys or secrets in code
- [ ] New features have tests (unit + acceptance)
- [ ] MCP tools use validated Pydantic inputs
- [ ] Path construction uses `.resolve()` with bounds checks
- [ ] Error messages are generic; details logged server-side
- [ ] State mutation in graph nodes returns `{**state}` copies
