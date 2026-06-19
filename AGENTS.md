# AGENTS.md — Berlin Insolvency Radar

This is the canonical operating guide for coding agents working in this repository.
Keep it specific, enforceable, and aligned with the actual repo automation.

## Project Identity

Berlin Insolvency Radar (BIRADAR) is an AI-powered insolvency intelligence system for Berlin.
It scrapes the official insolvency portal, extracts structured facts via LLM (DeepSeek),
enriches with public sources, scores opportunities deterministically, and exports
Markdown newsletter drafts.

The codebase is a Python 3.12+ MCP-first application with DuckDB persistence,
LangGraph orchestration, and a strict 6-layer architecture. Agents should preserve
that shape: pure domain logic in `domain/`, repository-isolated SQL in `storage/`,
LangGraph workflows in `graph/`, and thin transport handling in `mcp/`.

## Canonical Instruction Strategy

- `AGENTS.md` is the cross-agent source of truth.
- `QWEN.md`, `CLAUDE.md`, `GEMINI.md`, and `.github/copilot-instructions.md` should stay as thin bridge files that point back here.
- Qwen Code reads project-level skills and memory natively, so `QWEN.md` should remain a minimal bridge with no durable repo rules.
- Keep durable repo rules here; keep personal preferences out of committed files.
- Use path-scoped or workflow-specific agent files only when a narrow rule should not load in every session.

## Before Editing

1. Read this file and [README.md](README.md).
2. Check the worktree with `git status --short`; never overwrite user changes.
3. Read the relevant package before editing and keep existing package boundaries intact.
4. Run the narrowest useful validation before changes when feasible. Prefer `make check` for substantial work.
5. Follow the Test Mandate for every production-code change.

## Default Workflow

1. Restate the goal, constraints, affected files, and risks.
2. Pick the smallest cohesive change that solves the task.
3. Add or update tests first for production behavior changes.
4. Implement without broad refactors unless explicitly requested.
5. Validate with the relevant repo commands.
6. Handoff with changed files, checks run, skipped checks, and residual risk.

Pause for human review before broad architectural changes, destructive actions,
new dependencies, security-sensitive edits, or ambiguous behavior changes.

## Definition Of Done

- The requested scope is complete without unrelated refactors.
- Production-code changes include meaningful tests, and modified packages do not have 0% coverage.
- Formatting, lint, typecheck, and test commands relevant to the change pass.
- Documentation is updated when behavior, setup, commands, or agent workflow changes.
- No secrets or environment-specific private data are added.
- Final handoff names the checks run, skipped checks with reasons, and any follow-up risk.

## Naming

- Files: `snake_case.py`
- Test files: `test_<module>.py`
- Directories: `snake_case`
- Types: `PascalCase` (Pydantic models, classes)
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Acronyms: all caps: `HTTP`, `ID`, `URL`, `JSON`, `API`, `MCP`, `SQL`, `YAML`, `UUID`, `LLM`, `JSF`

## Structure

```
src/biradar/
  agents/         — LLM agent wrappers (DeepSeek extraction, risk review)
  cli/            — CLI entry point
  config/         — Typed configuration loading (Settings, AppConfig)
  domain/         — Pure functions with zero I/O (compliance, dedupe, scoring, statuses, validation)
  graph/          — LangGraph workflow definitions and state management
  mcp/            — MCP server, tools, schemas, and result envelopes
  observability/  — Structured logging
  output/         — Export generators (Markdown, JSON)
  services/       — Business logic orchestration (DI via AppContainer)
  sources/        — External data adapters (official portal scraper)
  storage/        — Database connection (DuckDB) and repository layer
  utils/          — Shared utilities (prompt loading, JSON parsing)
tests/
  unit/           — Fast, no I/O, mock LLM agents
  acceptance/     — Phase gating tests, real DuckDB
  e2e/            — Full pipeline, @pytest.mark.live for live portal
  fixtures/       — Test data and fixture builders
config/           — YAML config files (scoring.yaml, sources.yaml)
docs/             — Internal development docs (plans, reviews, research)
documentation/    — Tracked public user documentation
```

Layer rule:

```
cli/  →  mcp/  →  services/  →  graph/  →  agents/  →  domain/
                    ↓                         ↓
               storage/                   output/
               sources/
```

- Imports flow downward only. No circular dependencies.
- `domain/` modules have zero internal dependencies and zero side effects.
- All SQL lives in `storage/repository.py`. No raw SQL outside `storage/`.
- All services return `ResultEnvelope[T]` from `mcp/envelope.py`.
- DI via `AppContainer` (see `services/container.py`).

## Quality Gates

Use the commands that actually exist in this repo:

- `make format` — `ruff format src/biradar tests`
- `make format-check` — `ruff format --check src/biradar tests`
- `make lint` — `ruff check src/biradar tests`
- `make typecheck` — `pyright src/biradar`
- `make test` — unit tests with coverage
- `make test-acceptance` — acceptance tests with coverage
- `make test-e2e` — E2E tests (excludes `@pytest.mark.live`)
- `make check` — `format-check lint typecheck test test-acceptance test-e2e`

If a change is substantial, run `make check`. For targeted or docs-only work,
run the narrowest checks that prove the change is correct and call out anything skipped.

## Test Mandate

Every production-code change must include tests in the same push. No exceptions.

Requirements:

- Every modified production package must have tests committed in the same push.
- Use `pytest` with descriptive function names (`test_<unit>_<scenario>`).
- Use explicit stubs in tests when agent behavior must be deterministic; live tests use `@pytest.mark.live`.
- `make test` must pass before a production-code change is considered complete.
- Modified packages must show non-zero coverage.

Coverage targets by layer:

- `domain/` — 95%+
- `agents/`, `output/` — 50%+ (LLM-dependent modules; mock coverage)
- `services/` — 85%+
- `storage/` — 70%+
- `graph/` — 75%+
- `mcp/`, `cli/` — best effort

## Repository Rules

- Use `logging.getLogger(__name__)` for all modules.
- Use DuckDB parameterized queries (`?` placeholders) — never string interpolation.
- Do not modify an existing database migration; add a new migration instead.
- Keep all SQL in `storage/repository.py` and `storage/db.py`.
- LangGraph nodes must return new dict copies (`{**state}`), not mutated references.
- LLM calls must use `model_kwargs={"response_format": {"type": "json_object"}}` for DeepSeek.
- Wrap injected data in XML delimiters for prompt injection defense.
- Error messages in MCP responses must be generic; log details server-side.
- Validate all MCP inputs with Pydantic models in `mcp/schemas.py`.
- Use `Path.resolve()` with bounds checks for all file path construction.

## First Run

Prerequisites:

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

Setup:

```bash
uv sync --extra dev
cp .env.example .env
# Edit .env with your DEEPSEEK_API_KEY
```

Verify:

```bash
make check
```

Run the MCP server:

```bash
uv run biradar serve
```

Quick test (dry-run pipeline):

```bash
uv run biradar pipeline-check
```

## Commit Style

- `feat:` new feature for user or agent
- `fix:` bug fix
- `chore:` dependency bumps, tooling, CI
- `docs:` documentation only
- `refactor:` code change with no functional change
- `test:` adding or updating tests

## Validation And Handoff

When handing off work:

- State what changed and why.
- List checks run.
- List skipped checks and why they were skipped.
- Call out config changes, migrations, security impact, and residual risk.
