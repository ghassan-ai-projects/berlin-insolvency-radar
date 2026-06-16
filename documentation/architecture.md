# Architecture

## Overview

Berlin Insolvency Radar uses a 6-layer architecture designed for testability,
deterministic correctness, and MCP-first operation.

```
Layer 5 (Entry):     cli/main  ,  mcp/server
                         |            |
Layer 4 (Orch):     phase2_pipeline  ,  container (DI)
                         |       /     |    \
Layer 3 (Logic):     graph/  services/{health,candidates,issues,reviews,import_legacy}
                     /    |      \
Layer 2 (Adapters): agents/  domain/  output/  sources/
                     |        |
Layer 1 (Infra):    config/  observability/  storage/{db,repository}
```

All dependencies flow top-down. No circular imports.

## Layer Design

### Layer 1: Infrastructure
- `config/` — Typed configuration loading via Pydantic. `Settings` (project root, data dir) and `AppConfig` (scoring weights, source adapters).
- `observability/` — Structured logging with `logging.getLogger(__name__)`.
- `storage/db.py` — DuckDB connection and schema migrations.
- `storage/repository.py` — 8 repository classes centralizing all SQL. No raw SQL outside this file.

### Layer 2: Adapters
- `agents/` — LLM wrappers (DeepSeek). Extraction and risk review agents with JSON mode, structured fallback, and mock support.
- `domain/` — Pure functions with zero I/O: compliance filtering, hash-based deduplication, weighted scoring, status state machine, date validation.
- `output/` — Markdown and JSON export generators.
- `sources/` — External data adapters. `OfficialPortalAdapter` manages JSF sessions, ViewState extraction, CSRF replay, and HTML parsing.

### Layer 3: Services
- Business logic orchestration. Each service takes `Database` + config as constructor dependencies.
- All services return `ResultEnvelope[T]` from `mcp/envelope.py` — a typed `ok/data/errors/warnings/audit_id` wrapper.
- `AppContainer` in `services/container.py` is the composition root, wiring database, config, and repositories into all services.

### Layer 4: Workflow
- `graph/` — LangGraph state machines. `phase2_workflow.py` defines the 8-node agentic pipeline.
- `graph/state.py` — TypedDict-based workflow state with Literal-typed step tracking.
- `graph/checkpoints.py` — SQLite-backed checkpoint saver with WAL mode and 0o600 permissions.

### Layer 5: Entry Points
- `cli/main.py` — CLI argument parsing and command dispatch.
- `mcp/server.py` — MCP stdio server with 10 tools, Pydantic-validated inputs, and generic error responses.

## Key Design Decisions

### DuckDB as Source of Truth
Application state is owned by DuckDB, not by in-memory LangGraph checkpoints. Graph state carries only transient execution data (IDs, retry counts, step tracking). Durable facts (candidates, scores, evidence, audit events) are written to DuckDB within node execution.

### Deterministic Core
`domain/` modules are pure functions with no I/O, no LLM dependency, and no side effects. The compliance filter, deduplication, scoring formula, and status machine are all independently testable and immune to prompt injection.

### Fail-Closed Design
Errors quarantine candidates rather than passing them through:
- Extraction failures mark `is_consumer_likely=True` (safe default)
- Risk review failures return `passed_review=False`
- Scoring failures mark status `failed`
- Enrichment anti-bot blocks mark `blocked_by_anti_bot`

### MCP-First Interface
All functionality is exposed through typed MCP tools. The CLI calls the same service layer. Agents interact through the MCP server without knowing database paths or internals.

### Audit Trail
Every mutation logs to `audit_events` with actor, action, entity type, entity ID, request data, and result data. This provides forensic traceability for every state change.

## Repository Structure

```
src/biradar/
  agents/          LLM agent wrappers
    prompts/       RCTCO prompt templates (YAML)
  cli/             CLI entry point
  config/          Settings and AppConfig (Pydantic)
  domain/          Pure functions (compliance, dedupe, scoring, statuses, validation)
  graph/           LangGraph workflows and state
  mcp/             MCP server, tools, schemas, envelopes
  observability/   Structured logging
  output/          Markdown and JSON export generators
  services/        Business logic orchestration (AppContainer DI)
  sources/         External data adapters
  storage/         DuckDB connection and repository layer
  utils/           Shared utilities (prompt loading, JSON parsing)
tests/
  unit/            Fast tests, mock LLM agents
  acceptance/      Phase gating tests, real DuckDB
  e2e/             Full pipeline tests, @pytest.mark.live for live portal
  fixtures/        Test data and fixture builders
config/            YAML configuration files
```

## Dependency Injection

`AppContainer` (services/container.py) follows a simple constructor-injection pattern:

```python
class AppContainer:
    def __init__(self, config_dir: Path, db_path: Path):
        self.db = Database(db_path)
        self.config = load_config(config_dir)
        self.candidates = CandidateService(self.db)
        self.health = HealthService(self.db, self.config)
        self.issues = IssueService(self.db, db_path.parent / "exports")
        # ... etc
```

Entry points (CLI, MCP server) compose from this single root. No global singletons or module-level state.
