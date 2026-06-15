---
name: mcp-python-skeleton
description: Scaffold an MCP-first Python application with typed result envelopes, deterministic domain logic, and append-only audit logging.
source: auto-skill
extracted_at: '2026-06-15T16:57:49.082Z'
---

# MCP-First Python Application Skeleton

When building a new MCP-first Python application (especially for data pipelines, editorial intelligence, or agent-assisted workflows), follow this architecture to ensure safety, auditability, and type safety.

## 1. Core Principles
- **Agents suggest, code verifies, humans approve, logs remember.**
- Keep domain logic (scoring, filtering, status transitions) deterministic and separate from LLM/MCP layers.
- All state-changing operations must write an append-only audit event.
- Use a unified `ResultEnvelope` for all MCP tool responses to give agents predictable error handling and `next_action` hints.

## 2. Project Structure
```text
src/<project_name>/
  config/
    settings.py       # Pydantic models for YAML config loading
  domain/
    compliance.py     # Deterministic allowlists/quarantine rules
    scoring.py        # Deterministic formula engines
    statuses.py       # State machine transition validation
  storage/
    db.py             # DuckDB connection and schema migrations
    repository.py     # Centralized CRUD (no ad-hoc SQL in services)
  services/
    container.py      # Dependency injection container
    health.py         # Health/readiness checks
    reviews.py        # Business logic for state changes + audit writes
  mcp/
    envelope.py       # Unified ResultEnvelope[Generic[T]]
    server.py         # MCP server definition and tool routing
  graph/
    state.py          # TypedDict LangGraph state models
    workflows.py      # LangGraph orchestration shells
```

## 3. Typed Result Envelope Pattern
All MCP tools and services must return this envelope to ensure agents can safely parse successes, warnings, and actionable errors.

```python
from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class ResultEnvelope(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    audit_id: str | None = None
    next_action: str | None = None
```

## 4. Audit Logging Requirement
Every state-changing service method must log an event before returning:

```python
audit_id = self.audit_repo.log_event(
    actor=actor,
    action="entity_updated",
    entity_type="candidate",
    entity_id=entity_id,
    request_data={"decision": decision},
    result_data={"new_status": new_status},
)
```

## 5. Legacy Data & Idempotent Import Enforcement
When importing from legacy or external databases, enforce strict immutability and true idempotency:
1. **Path Guard**: Reject if `legacy_db_path` resolves to the active repo database path.
2. **Pre-flight Hash**: Compute pre-import file size, mtime, and SHA-256 hash.
3. **Read-Only Connection**: Open the legacy connection strictly with `duckdb.connect(path, read_only=True)`.
4. **True Idempotency**: Deduplication must handle both *intra-run* duplicates (using an in-memory `set` of computed keys) AND *cross-run* duplicates. Before creating a new candidate, query `candidate_repo.get_by_id(dedupe_key_id)`. If it exists, increment the duplicate count, link the new `raw_record` to the existing candidate, and `continue` without upserting a new candidate row.
5. **Post-flight Verification**: After the run, verify size, mtime, and hash are identical to the pre-flight state. Fail hard and abort if mutated.
6. **Graceful Degradation on Failure**: If the import crashes midway, ensure the `source_run` is marked as `failed` with an `error_json` and an audit event is logged, preventing silent data corruption.

## 6. Testing Strategy
- **Unit Tests**: Cover deterministic domain modules (scoring formulas, status transitions, compliance allowlists) to 95%+ coverage.
- **Deterministic Fixtures**: Do not commit binary database files. Instead, provide a Python script (e.g., `build_legacy_fixture.py`) that reads a JSON fixture and generates a temporary DuckDB file on the fly during test setup. This ensures reproducibility and clean Git history.
- **Acceptance Tests**: Verify end-to-end MCP happy paths using temporary DuckDB files. Assert that `radar_health` returns a useful `next_action` on a fresh database, and that cross-run idempotency holds.

## 7. Quality Gates (`Makefile`)
Enforce via CI/local pre-commit:
```makefile
check: format lint typecheck test

format:
	ruff format src tests

lint:
	ruff check src tests

typecheck:
	pyright src

test:
	pytest tests/unit --cov=src --cov-report=term-missing
```
Use `typeCheckingMode = "basic"` in `pyproject.toml` for Pyright to balance strictness with LangGraph/Pydantic typing quirks.
