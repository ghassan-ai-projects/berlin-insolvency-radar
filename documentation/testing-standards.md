# Testing Standards

## Test Tiers

| Tier | Location | Characteristics | Speed |
|------|----------|-----------------|-------|
| Unit | `tests/unit/` | No I/O, explicit stubs where needed, fast | <2s |
| Acceptance | `tests/acceptance/` | Real DuckDB, fixture data, phase gates | <5s |
| E2E (local) | `tests/e2e/` | Full pipeline, fixture/stub mode | <5s |
| E2E (live) | `tests/e2e/` | Live portal + DeepSeek, `@pytest.mark.live` | ~30s |

## Conventions

- Test files: `test_<module>.py`
- Test functions: `test_<unit>_<scenario>` (descriptive, snake_case)
- Use `pytest` fixtures for setup; `conftest.py` for shared fixtures
- Live E2E tests are gated by `@pytest.mark.live` and load `DEEPSEEK_API_KEY` from `.env`

## Coverage Targets

| Layer | Target | Rationale |
|-------|--------|-----------|
| `domain/` | 95%+ | Pure functions, zero I/O — should be fully covered |
| `services/` | 85%+ | Business logic orchestration |
| `graph/` | 75%+ | Workflow definition and routing |
| `storage/` | 70%+ | Repository layer, SQL access |
| `agents/` | 50%+ | LLM-dependent; mock coverage for fallback paths |
| `output/` | 50%+ | File I/O; test output generation logic |
| `mcp/`, `cli/` | Best effort | Thin transport and argument parsing |

## Running Tests

```bash
make test              # Unit tests
make test-acceptance   # Acceptance tests
make test-e2e          # E2E (excludes live)
make check             # Format + lint + typecheck + unit + acceptance + non-live E2E

# Live E2E (requires DEEPSEEK_API_KEY)
uv run pytest tests/e2e -m "live" -v
```

## Test Stub Behavior

- Production code no longer substitutes fake LLM outputs when `DEEPSEEK_API_KEY` is missing.
- Tests that need deterministic agent behavior inject explicit stub extractor/reviewer/enricher functions.
- Enrichment can be disabled in `config/sources.yaml`, in which case the system skips it without inventing data.

## Phase Acceptance Gates

Each development phase has defined acceptance tests:

- **Phase 0:** 7 tests — database boot, health tool, envelope stability, MCP server, audit events, config loading, workflow runtime
- **Phase 1:** 12 tests — legacy import (dry-run, real, idempotent, rollback), corporate filter, candidate listing/detail, review (approve/reject), status transitions, issue draft, export, audit trail, health reporting
- **Phase 2:** 6 E2E tests — pipeline dry-run, quarantine exclusion, fixture persistence, check command, MCP workflow tool, live portal (gated)
