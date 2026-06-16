# Repo State Assessment — 2026-06-16

## Scope

This assessment answers four questions:

1. What is the current state of the repo?
2. Is it ready to open publicly?
3. Is it working now?
4. Is the LangGraph dependency justified?

The conclusions below are based on direct code inspection and local validation run on 2026-06-16.

## Executive Verdict

The repository is publishable as an **experimental pre-release project**, but it is **not ready to present as a fully working or production-hardened system**.

The codebase has good structural discipline:

- clear package boundaries
- governance files present
- CI workflow present
- fixture-backed end-to-end flow works
- unit coverage is meaningful in core areas

But there are still release blockers for a public "works out of the box" claim:

- lint is currently failing
- acceptance tests are currently failing
- the README includes a broken CLI command
- the documented `make check` path does not work in a plain shell here
- live portal/API behavior was not verified in this assessment
- the main happy path currently depends heavily on mock/fallback agent behavior unless a real DeepSeek key is configured

## Validation Summary

Commands run:

- `uv run pytest tests/unit --cov=src/biradar --cov-report=term-missing --timeout=30`
- `uv run pytest tests/acceptance --cov=src/biradar --cov-report=term-missing --timeout=30`
- `uv run pytest tests/e2e -m 'not live' --cov=src/biradar --cov-report=term-missing --timeout=60`
- `uv run pyright src/biradar`
- `uv run ruff check src/biradar tests`
- `uv run biradar --help`
- `uv run biradar phase2-check`

Observed results:

- Unit tests: pass (`51 passed`)
- Acceptance tests: fail (`2 failed, 18 passed`)
- Non-live E2E tests: pass (`5 passed, 1 deselected`)
- Typecheck: pass (`0 errors`)
- Lint: fail
- CLI help: works
- `phase2-check`: works in fixture/mock mode

Important nuance:

- `make test`, `make lint`, `make typecheck`, and `make test-acceptance` failed when run directly because `pytest`, `ruff`, and `pyright` were not on `PATH`.
- The repo is therefore currently validated through `uv run ...`, not through plain `make ...`, despite [README.md](/Users/ghassan/my-projects/berlin-insolvency-radar/README.md:35) presenting `make check` as the primary verification path.

## What Is Working

The following claims are supported by direct validation:

- The Python package resolves and runs through `uv`.
- The MCP/CLI surface is implemented and callable.
- The fixture-backed Phase 2 pipeline executes end to end.
- The DuckDB-backed persistence path works in non-live E2E fixture mode.
- The Phase 2 verification helper completes successfully and writes exports.
- Static typing is currently clean under `pyright`.

Evidence:

- [src/biradar/cli/main.py](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/cli/main.py:17) defines working CLI commands including `phase2-run`, `phase2-check`, and `serve-mcp`.
- [tests/e2e/test_phase2_pipeline.py](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/e2e/test_phase2_pipeline.py:10) covers dry-run, fixture persistence, and the `phase2-check` path.

## What Is Not Working Cleanly

### 1. Lint is failing

`ruff check` currently fails on unused and unsorted imports in [tests/unit/test_enrichment.py](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/unit/test_enrichment.py:3).

Impact:

- CI should currently fail on the lint job
- the repo does not meet its own documented quality gate for public consumption

### 2. Acceptance tests are stale against the current schema

[tests/acceptance/test_phase0_foundation.py](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/acceptance/test_phase0_foundation.py:68) and [tests/acceptance/test_phase0_foundation.py](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/acceptance/test_phase0_foundation.py:178) still assert schema version `002_audit_table`, while the database now reports `003_enrichments` via [src/biradar/storage/db.py](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/storage/db.py:32).

Impact:

- acceptance tests are red for a non-behavioral reason
- the repo currently advertises a validation story that does not hold end to end
- this weakens confidence in other tests because it shows maintenance drift

### 3. README documents a broken server command

[README.md](/Users/ghassan/my-projects/berlin-insolvency-radar/README.md:48) tells users to run `uv run biradar serve`, but the CLI actually exposes `serve-mcp` in [src/biradar/cli/main.py](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/cli/main.py:37).

Impact:

- first-time users will hit an avoidable failure
- this is a public-readiness blocker because it affects the primary setup path

### 4. Export filenames can collide

[src/biradar/output/export.py](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/output/export.py:100) and [src/biradar/output/export.py](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/output/export.py:133) generate export filenames with second-level timestamp granularity only.

During `uv run biradar phase2-check`, two pipeline runs completed within the same second and reused the same export paths.

Impact:

- later runs can overwrite earlier artifacts
- local auditability is weaker than the project claims
- this is small to fix but should be fixed before stronger public claims

### 5. "Working" currently means fixture-backed and mock-friendly

The project does work in local mock/fixture mode, but the live value proposition depends on:

- the official insolvency portal staying compatible
- real DeepSeek credentials being present
- optional live enrichment sources remaining reachable

This assessment did not verify the live portal path or live DeepSeek path. The live test exists in [tests/e2e/test_phase2_live_e2e.py](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/e2e/test_phase2_live_e2e.py:24), but it was not run here.

Impact:

- "works locally with fixtures" is supported
- "works live today against the real portal and LLM" is not confirmed by this assessment

## Public Readiness Assessment

### Ready enough to publish

The repo already has the baseline open-source surface area:

- [LICENSE](/Users/ghassan/my-projects/berlin-insolvency-radar/LICENSE:1)
- [CONTRIBUTING.md](/Users/ghassan/my-projects/berlin-insolvency-radar/CONTRIBUTING.md:1)
- [SECURITY.md](/Users/ghassan/my-projects/berlin-insolvency-radar/SECURITY.md:1)
- [CODE_OF_CONDUCT.md](/Users/ghassan/my-projects/berlin-insolvency-radar/CODE_OF_CONDUCT.md:1)
- [SUPPORT.md](/Users/ghassan/my-projects/berlin-insolvency-radar/SUPPORT.md:1)
- GitHub Actions CI in [.github/workflows/ci.yml](/Users/ghassan/my-projects/berlin-insolvency-radar/.github/workflows/ci.yml:1)
- `.env` ignored and `.env.example` present

That is enough to open the repo publicly if it is labeled honestly as:

- pre-release
- experimental
- fixture-backed for local verification
- not yet production-hardened

### Not ready for a stronger public claim

It is not ready to market as "fully working" or "production ready" because:

- local quality gates are red
- docs contain at least one broken command
- live path was not confirmed
- several components still rely on mock fallback behavior for developer convenience

## Is LangGraph Justified?

### Short answer

**Partially justified for Phase 2, not justified for the smaller workflows in its current form.**

### Where LangGraph is earning its keep

The strongest case is the Phase 2 pipeline in [src/biradar/graph/phase2_workflow.py](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/phase2_workflow.py:362):

- there is a multi-step stateful workflow
- there is conditional routing from `risk_review` back to `extraction`
- checkpointing/resume is an intended feature via [src/biradar/graph/checkpoints.py](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/checkpoints.py:1)
- the project concept is explicitly workflow-oriented

That means LangGraph is not random architecture theater here. There is at least one real graph concern: stateful retry routing.

### Where the justification is weak

The current graph is still mostly a linear pipeline:

- `ingest -> normalize_and_compliance -> dedupe -> extraction -> enrichment -> scoring -> risk_review -> draft_assembly -> export`
- only one conditional edge exists
- no parallel branches are used
- most nodes are simple wrappers around ordinary Python functions

The Phase 0 and review workflows are especially weak uses of LangGraph:

- [src/biradar/graph/phase0_workflow.py](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/phase0_workflow.py:56) is effectively a one-node health check
- [src/biradar/graph/review_workflow.py](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/review_workflow.py:43) is a thin wrapper around a service call with trivial loop logic

### Assessment

If the roadmap genuinely includes:

- resumable long-running runs
- richer retry loops
- human-in-the-loop checkpoints
- branch-specific recovery paths
- multiple agent stages with state inspection

then keeping LangGraph is reasonable.

If not, the current implementation is carrying graph complexity earlier than necessary, especially outside Phase 2.

My view:

- keep LangGraph for `phase2_workflow`
- avoid expanding it further until live workflow complexity proves it necessary
- consider removing or de-emphasizing LangGraph in the Phase 0 and review shells if simplicity becomes a priority

## Release Recommendation

Recommended status for a public opening today:

- **Yes** to opening the repository publicly as an experimental project
- **No** to presenting it as fully working production software

Minimum fixes before a stronger public launch:

1. Fix lint failures.
2. Update stale acceptance assertions for the current schema version.
3. Fix the README command `uv run biradar serve` to `uv run biradar serve-mcp`.
4. Make export filenames collision-safe.
5. Re-run CI-equivalent checks and confirm green.
6. Run and record one current live portal verification with exact date and outcome.

## Final Assessment

As of 2026-06-16, Berlin Insolvency Radar is a credible pre-release codebase with solid structure and a working fixture-backed pipeline, but it is not yet in a "public users can trust every documented path" state.

The most accurate description today is:

> Publicly shareable, technically promising, locally verifiable in mock/fixture mode, but not yet fully release-ready.
