# Phase 0 Review

**Date:** 2026-06-15
**Reviewer:** Codex
**Scope:** Phase 0 foundation, quality, tests, safety, and completeness against `docs/strategy/phase-acceptance-tests.md` and `docs/strategy/phase-0-implementation-plan.md`.

## Verdict

Phase 0 is complete as of the follow-up fixes on 2026-06-15.

The core skeleton exists, the MCP-facing tool path is covered by acceptance tests, the minimal LangGraph workflow succeeds and writes an audit marker, and the single Phase 0 gate passes under the declared `uv` Python 3.12 environment.

The correct command for local verification is:

```bash
uv run make phase0-check
```

`make check` now aliases the same Phase 0 gate.

## What Is Working

- Fresh DuckDB initialization creates the expected Phase 0 tables.
- Typed config loading works for the default scoring and sources config.
- Health service works on a fresh DB and returns a useful `next_action`.
- Audit events can be written and read through the MCP tool path.
- MCP server construction and the exact v0 tool list are covered by acceptance tests.
- The Phase 0 LangGraph health workflow returns a successful typed final state, writes a workflow audit marker, and does not create candidates or source runs.
- Unit tests cover the deterministic domain modules for compliance, scoring, and status transitions.
- The declared Python 3.12 `uv` environment runs format, lint, typecheck, unit tests, and acceptance tests successfully.
- Safety defaults include a guard preventing the active radar DB from being used as the legacy import input.

## Findings

### P1: Acceptance Tests Do Not Exercise The MCP Tool Layer

Phase 0 explicitly says the MCP server/tool layer must respond, and the envelope gate is defined for "any v0 MCP tool handler." The current acceptance tests call services and repositories directly instead of invoking `create_mcp_server` handlers.

Evidence:

- Acceptance spec requires MCP/tool behavior: `docs/strategy/phase-acceptance-tests.md:52-55`, `docs/strategy/phase-acceptance-tests.md:102-121`, `docs/strategy/phase-acceptance-tests.md:176-177`.
- Current tests call `container.health.check()`, `container.candidates.get_candidate()`, and `container.audit_repo.get_events()` directly: `tests/acceptance/test_phase0_foundation.py:60-84`, `tests/acceptance/test_phase0_foundation.py:87-102`.
- MCP handlers live in `src/biradar/mcp/server.py:175-257`, but no acceptance test invokes them.

Impact: the tests can pass while the OpenClaw-facing MCP surface is broken, inconsistent, or unable to serialize/handle validation errors correctly.

Recommended fix: add acceptance coverage that creates the MCP server, lists exactly the expected tools, calls `radar_health`, calls `radar_audit_trail`, and verifies success and validation failure envelopes after JSON serialization.

Status: Fixed. `tests/acceptance/test_phase0_foundation.py` now verifies the exact MCP tool list, server construction, `radar_health`, `radar_audit_trail`, and a stable validation error envelope through the shared MCP handler path.

### P1: LangGraph Gate Is Too Weak And Misses Required Audit Marker

The Phase 0 spec requires a no-op or health-check LangGraph workflow that returns a typed final state, records a workflow/audit marker, and does not write candidate/source records. The current acceptance test invokes the review workflow with a fake candidate and asserts failure.

Evidence:

- Spec requirement: `docs/strategy/phase-acceptance-tests.md:150-158`.
- Current test accepts a failed review: `tests/acceptance/test_phase0_foundation.py:114-131`.
- The workflow calls `container.reviews.review_candidate(...)` and returns `failed` when the candidate does not exist: `src/biradar/graph/review_workflow.py:13-29`.
- No workflow-specific audit marker is written in the workflow itself: `src/biradar/graph/review_workflow.py:9-44`.

Impact: this proves LangGraph can import and return an error, but not that the Phase 0 workflow shell is integrated in the intended safe, auditable way.

Recommended fix: add a dedicated Phase 0 health/no-op workflow, or update the review workflow test to seed a valid candidate and assert final typed state plus an audit/workflow marker. For Phase 0, a no-op health workflow is cleaner because candidate review is explicitly not required yet.

Status: Fixed. `src/biradar/graph/phase0_workflow.py` implements a safe Phase 0 health workflow, and acceptance tests assert success, typed state fields, audit marker retrieval, and no candidate/source-run writes.

### P1: `make check` Does Not Run The Phase 0 Acceptance Gates

The Phase 0 done definition requires all Phase 0 acceptance tests and `make check` to pass. Current `make check` runs formatting, lint, typecheck, and unit tests only.

Evidence:

- Done definition: `docs/strategy/phase-acceptance-tests.md:171-174`.
- Make target excludes acceptance tests: `Makefile:3-15`.
- Acceptance tests are available only through a separate target: `Makefile:20-21`.

Impact: a developer can run the advertised check target and miss the actual product gate.

Recommended fix: either include `test-acceptance` in `check`, or add a `phase0-check` target that runs `format`, `lint`, `typecheck`, `test`, and `test-acceptance`.

Status: Fixed. `Makefile` now has `phase0-check`, and `check` aliases it.

### P1: Clean Setup Is Not Documented Enough To Be Reproducible

The repo declares Python 3.12+ and dependencies in `pyproject.toml`, but there is no lockfile or README guidance for creating the environment. On this machine, plain `pytest` is not on PATH, plain `make check` cannot find `ruff`, and system `python3` is 3.9.6.

Evidence:

- `pytest tests/unit ...` failed with `zsh:1: command not found: pytest`.
- `make check` failed with `make: ruff: No such file or directory`.
- `python3 --version` reported `Python 3.9.6`.
- `env PYTHONPATH=src python3 -m pytest ...` failed on Python 3.9 syntax/dependency issues.
- `uv run make check` passed after using the declared Python 3.12 environment.
- README currently contains only a one-sentence project description.

Impact: a new developer or agent can verify the project only if they infer the `uv run ...` workflow.

Recommended fix: document the exact setup and verification commands, for example:

```bash
uv sync --extra dev
uv run make check
uv run make test-acceptance
uv run biradar
```

Status: Fixed. `README.md` now documents `uv sync --extra dev`, `uv run make phase0-check`, CLI startup checks, MCP tool listing, MCP stdio startup, and safety defaults.

### P2: CLI Startup Works But Has A Polish Bug And Does Not Start MCP

`uv run biradar` successfully loads config, but prints `Loaded config for biradar vv1`. More importantly, the CLI is only a config smoke test; it does not expose a command to start the MCP server.

Evidence:

- CLI prints `v{config.scoring.version}`, while the config version is already `v1`: `src/biradar/cli/main.py:11-13`.
- MCP server factory exists, but CLI does not call it: `src/biradar/mcp/server.py:13-259`.

Impact: this is not a correctness blocker for storage/config, but it weakens the "MCP server can start locally" done criterion.

Recommended fix: add a CLI subcommand or documented module entrypoint for starting the MCP server locally, then smoke-test it in acceptance or a separate MCP test.

Status: Fixed. The CLI now supports `check`, `mcp-info`, and `serve-mcp`. The startup message is corrected to `Loaded config for biradar v1`.

### P2: Implementation Plan And Code Are Out Of Sync

The implementation plan asks for `storage/audit.py` and minimal `graph/import_workflow.py`; the code centralizes audit in `storage/repository.py` and only includes `graph/review_workflow.py`.

Evidence:

- Plan asks for `storage/audit.py`: `docs/strategy/phase-0-implementation-plan.md`.
- Plan asks for `graph/import_workflow.py` and `graph/review_workflow.py`: `docs/strategy/phase-0-implementation-plan.md`.
- Current files include `src/biradar/storage/repository.py`, `src/biradar/graph/review_workflow.py`, and no `src/biradar/graph/import_workflow.py`.

Impact: not necessarily wrong, but it makes phase tracking ambiguous. If the implementation plan is authoritative, Phase 0 is incomplete. If the acceptance spec is authoritative, document the deviation.

Recommended fix: either add the missing files or update the Phase 0 plan to reflect the repository-based audit implementation and chosen workflow shell.

Status: Fixed. The implementation plan now marks Phase 0 complete, documents repository-layer audit writes, and names the Phase 0 health workflow.

### P2: Extra Phase 1-ish Services Have Low Coverage

The repository includes legacy import, review, and issue services even though Phase 0 does not require them. Acceptance coverage for the full service layer is low, and the import service currently simulates import counts rather than persisting candidates.

Evidence:

- Phase 0 explicitly does not require legacy import, candidate review, scoring approval, or issue generation: `docs/strategy/phase-acceptance-tests.md:60`.
- Acceptance coverage run reported overall coverage of 56%; issue service 17%, candidates 37%, legacy import 40%, reviews 42%.
- `LegacyImportService` comments state that it only simulates mapping for v0 and a full Phase 1 implementation would insert records: `src/biradar/services/import_legacy.py:85-99`.

Impact: this is acceptable if those paths are treated as scaffolding only. It is risky if anyone assumes Phase 1 behavior is already implemented.

Recommended fix: label these as incomplete Phase 1 scaffolding in docs, or add Phase 1 fixtures/tests before using them in workflow demos.

## Verification Results

Current commands that pass:

```bash
uv run make phase0-check
uv run make check
uv run pyright src/biradar
uv run --python 3.12 pytest tests/unit
uv run --python 3.12 pytest tests/acceptance
uv run --python 3.12 ruff check src/biradar tests
uv run biradar check
uv run biradar mcp-info
```

Key results:

- `uv run make phase0-check`: passed; Ruff format/check passed, Pyright passed, 9 unit tests passed, 8 acceptance tests passed.
- `uv run biradar check`: exited successfully, printed `Loaded config for biradar v1`.
- `uv run biradar mcp-info`: exited successfully and listed the 8 v0 MCP tools.

Commands that failed in the ambient shell:

```bash
pytest tests/unit --cov=src/biradar --cov-report=term-missing
pytest tests/acceptance --cov=src/biradar --cov-report=term-missing
make check
env PYTHONPATH=src python3 -m pytest tests/unit --cov=src/biradar --cov-report=term-missing
env PYTHONPATH=src python3 -m pytest tests/acceptance --cov=src/biradar --cov-report=term-missing
```

Failure reasons:

- `pytest` was not on PATH.
- `ruff` was not on PATH for plain `make check`.
- System `python3` is Python 3.9.6, below the declared `>=3.12`.
- Dependencies such as `pydantic` were not installed in the ambient Python environment.

## Completion Checklist

All Phase 0 completion items from the initial review are done:

- MCP-level acceptance tests cover `radar_health`, `radar_audit_trail`, tool listing, and stable error envelopes.
- The Phase 0 LangGraph workflow succeeds, returns typed final state, writes an audit/workflow marker, and does not create candidates/source records.
- Acceptance tests are included in a single documented phase gate: `uv run make phase0-check`.
- README instructions cover setup, verification, fresh DB boot, MCP server startup, and safety defaults.
- MCP startup is available through `uv run biradar serve-mcp`; `uv run biradar mcp-info` provides a non-blocking startup smoke check.
- The CLI startup message is fixed.
- The implementation plan reflects the actual Phase 0 audit and workflow structure.

Residual note for Phase 1: legacy import, review, and issue generation services remain scaffolding until Phase 1 fixtures and acceptance tests are added.
