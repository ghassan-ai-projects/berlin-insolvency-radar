# Implementation Backlog

**Date:** 2026-06-19
**Purpose:** Turn the operationalization plan into an executable backlog with ordering, dependencies, affected files, and validation

## Priority Model

- `P0` blocks dependable live operation
- `P1` materially improves reliability and maintainability
- `P2` improves product quality and expansion readiness
- `P3` proves business value after the operational core is stable

## Execution Order

1. P0.1 Green the repo gate
2. P0.2 Add explicit live runtime modes
3. P0.3 Add stage-level run reporting
4. P0.4 Harden model timeout/retry/failure handling
5. P0.5 Split parser strategies and capture live fixtures
6. P1.1 Introduce provider-neutral LLM adapter
7. P1.2 Refactor enrichment into registry/adapters
8. P1.3 Add Unternehmensregister
9. P1.4 Add OpenCorporates
10. P1.5 Normalize source-claim storage
11. P2.1 Tighten workflow typing
12. P2.2 Improve MCP/application boundary
13. P2.3 Build extraction/compliance eval set
14. P3.1 Produce weekly issues and run user validation

## Execution Status Snapshot

Completed in code on 2026-06-19:

- P0.2 Add explicit live runtime modes
- P0.3 Add stage-level run reporting
- P0.4 Harden model timeout/failure classification
- P0.5 Split parser strategies and classify portal responses
- P1.1 Introduce provider-neutral LLM adapter
- P1.2 Refactor enrichment into registry/adapters
- P1.5 Normalize source-claim storage
- P1.4 partially superseded by `north_data` and `wikidata` source additions
- P1.x Enrichment source config upgraded from boolean flags to per-source contracts

Still remaining:

- P0.1 Green the full repo gate with `make check`
- P1.3 Add Unternehmensregister runtime adapter
- P2.x typing, MCP boundary, and eval-set work
- P3.1 recurring issue production and market validation

## P0

### P0.1 Green The Repo Gate

**Goal:** Make the documented quality gate truthful again.

**Why now:** `make check` currently fails, so the repo cannot honestly claim a green baseline.

**Files likely affected:**

- [`src/biradar/agents/extraction.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/extraction.py:1)
- [`src/biradar/agents/risk_review.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/risk_review.py:1)
- [`src/biradar/graph/pipeline_workflow.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/pipeline_workflow.py:1)

**Work:**

1. Run `make format`
2. Re-run `make check`
3. Fix any secondary breakage if formatting exposes it

**Validation:**

```bash
make check
```

**Done when:** `make check` passes.

### P0.2 Add Explicit Live Runtime Modes

**Goal:** Separate portal acquisition failures from full model-path failures.

**Why now:** live validation showed the portal path can succeed while the model stage still fails.

**Files likely affected:**

- [`src/biradar/cli/main.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/cli/main.py:1)
- [`src/biradar/services/pipeline.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/services/pipeline.py:1)
- [`tests/e2e/test_live_pipeline.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/e2e/test_live_pipeline.py:1)

**Work:**

1. Add CLI modes or flags for:
   - `portal-only`
   - `portal-with-stubs`
   - `full-live`
2. Support `--max-records` consistently in live smoke paths
3. Ensure outputs clearly state which mode was used

**Validation:**

```bash
uv run biradar live-smoke-portal --start-date 2026-06-17 --end-date 2026-06-19
uv run biradar live-smoke-full --start-date 2026-06-17 --end-date 2026-06-19 --max-records 3
```

**Done when:** portal-only and full-live can be invoked separately and produce distinct outcomes.

### P0.3 Add Stage-Level Run Reporting

**Goal:** Make failures diagnosable by stage.

**Why now:** current live failure surfaced as a long timeout inside the pipeline, not as a clean operational report.

**Files likely affected:**

- [`src/biradar/services/pipeline.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/services/pipeline.py:1)
- [`src/biradar/graph/pipeline_workflow.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/pipeline_workflow.py:1)
- [`src/biradar/storage/db.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/storage/db.py:1)

**Work:**

1. Record per-stage start/end/duration/status
2. Return a run summary in CLI output and workflow results
3. Persist minimal run-stage metadata

**Validation:**

- portal-only run shows fetch/parse timings
- full-live run shows where it failed

**Done when:** every run yields a stage report.

### P0.4 Harden Model Timeout/Retry/Failure Handling

**Goal:** Stop model calls from being opaque long blockers.

**Why now:** the full live E2E timed out in extraction.

**Files likely affected:**

- [`src/biradar/agents/extraction.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/extraction.py:1)
- [`src/biradar/agents/risk_review.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/risk_review.py:1)
- [`src/biradar/services/pipeline.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/services/pipeline.py:1)

**Work:**

1. Add explicit model call timeout
2. Add bounded retry behavior
3. Distinguish:
   - provider timeout
   - provider auth/config error
   - invalid response payload
   - model refusal/empty response
4. Fail with classified stage errors

**Validation:**

- targeted unit tests with mocked slow/failing LLM
- live smoke rerun

**Done when:** model failures are classified and bounded.

### P0.5 Split Parser Strategies And Capture Live Fixtures

**Goal:** Make portal parsing robust to current and future shape variation.

**Why now:** the current parser is too tied to one structure.

**Files likely affected:**

- [`src/biradar/sources/official_portal.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/sources/official_portal.py:1)
- [`tests/unit/test_official_portal.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/unit/test_official_portal.py:1)
- `tests/fixtures/official_portal/*`

**Work:**

1. Split fetch from parse
2. Add parser strategies:
   - HTML table
   - JSF partial-response
   - span/div result list
   - portal error pages
3. Capture dated live fixtures
4. Add classification for:
   - too many results
   - form returned again
   - blocked
   - no matches

**Validation:**

```bash
uv run pytest tests/unit/test_official_portal.py -v
```

**Done when:** parser tests cover all known response types.

## P1

### P1.1 Introduce Provider-Neutral LLM Adapter

**Goal:** Remove direct provider construction from business logic.

**Files likely affected:**

- [`src/biradar/agents/extraction.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/extraction.py:1)
- [`src/biradar/agents/risk_review.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/risk_review.py:1)
- [`src/biradar/services/container.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/services/container.py:1)
- new `src/biradar/agents/llm.py`

**Work:**

1. Define `StructuredLLM` protocol
2. Add provider factory
3. Move config/provider choice to DI
4. Keep DeepSeek as default initially

**Validation:**

- unit tests with fake provider
- non-live pipeline tests still pass

**Done when:** extraction/review no longer construct `ChatOpenAI` directly.

### P1.2 Refactor Enrichment Into Registry/Adapters

**Goal:** Make source expansion cheap.

**Files likely affected:**

- [`src/biradar/sources/enrichment.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/sources/enrichment.py:1)
- new `src/biradar/sources/enrichment/` package
- [`tests/unit/test_enrichment.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/unit/test_enrichment.py:1)

**Work:**

1. Split into:
   - `models.py`
   - `registry.py`
   - `orchestrator.py`
   - one file per source
2. Add normalized `SourceClaim` / `SourceResult`
3. Move current sources into adapter modules

**Validation:**

```bash
uv run pytest tests/unit/test_enrichment.py -v
```

**Done when:** one new source can be added as one module plus one registry entry.

### P1.3 Add Unternehmensregister

**Goal:** Add the best official secondary source.

**Files likely affected:**

- new `src/biradar/sources/acquisition/unternehmensregister.py`
- new tests and fixtures
- [`config/sources.yaml`](/Users/ghassan/my-projects/berlin-insolvency-radar/config/sources.yaml:1)

**Work:**

1. Implement adapter
2. Use as secondary acquisition and/or corroboration
3. Add live-safe smoke coverage if feasible

**Validation:**

- fixture-backed tests
- one targeted live smoke if practical

**Done when:** Unternehmensregister works through the new adapter architecture.

### P1.4 Add OpenCorporates

**Goal:** Add easy normalization and provenance-rich enrichment.

**Files likely affected:**

- new `src/biradar/sources/enrichment/opencorporates.py`
- config updates
- tests

**Work:**

1. Implement OpenCorporates adapter
2. Map response into normalized claims
3. Use for identity reconciliation and cross-checking

**Validation:**

- mocked adapter tests
- optional integration smoke with API key if available

**Done when:** OpenCorporates is available as a first-class enrichment source.

### P1.5 Normalize Source-Claim Storage

**Goal:** Persist real claim lineage instead of only merged enrichment fields.

**Files likely affected:**

- [`src/biradar/storage/db.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/storage/db.py:1)
- [`src/biradar/storage/repository.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/storage/repository.py:1)
- pipeline persistence paths

**Work:**

1. Add new migration for source claims
2. Persist source-level claims and provenance
3. Keep merged summary fields as a convenience layer

**Validation:**

- migration test
- acceptance/E2E persistence checks

**Done when:** source claim lineage is queryable.

## P2

### P2.1 Tighten Workflow Typing

**Goal:** Reduce silent state drift.

**Files likely affected:**

- [`src/biradar/graph/state.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/state.py:1)
- [`src/biradar/graph/pipeline_workflow.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/pipeline_workflow.py:1)

**Work:**

1. Replace generic `dict` payloads with typed models where practical
2. Reduce ad hoc state mutation

**Validation:**

- unit and E2E workflow tests

**Done when:** core state is more explicit and less fragile.

### P2.2 Improve MCP/Application Boundary

**Goal:** Make MCP transport thinner and application services clearer.

**Files likely affected:**

- [`src/biradar/mcp/server.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/mcp/server.py:1)
- services layer

**Work:**

1. Reduce orchestration logic in server dispatch
2. Keep service contracts stable and generic
3. Improve workflow-tool result envelopes

**Validation:**

- MCP E2E tests

**Done when:** transport concerns and app concerns are cleaner.

### P2.3 Build Extraction/Compliance Eval Set

**Goal:** Measure whether the output is trustworthy.

**Files likely affected:**

- new eval fixtures/docs/tests

**Work:**

1. Build labeled recent filing sample
2. Record expected extraction fields and compliance labels
3. Compute metrics

**Validation:**

- reproducible eval run

**Done when:** metrics exist in `docs/`.

## P3

### P3.1 Produce Weekly Issues And Run User Validation

**Goal:** Prove this is a product, not just a pipeline.

**Work:**

1. Produce 3 to 4 weekly issues from live or recent data
2. Review with target users
3. Capture usefulness, novelty, actionability

**Validation:**

- feedback summary in docs

**Done when:** product direction is chosen from evidence.

## Sprint Proposal

### Sprint 1

- P0.1 Green the repo gate
- P0.2 Add explicit live runtime modes
- P0.3 Add stage-level run reporting
- P0.4 Harden model timeout/retry/failure handling

### Sprint 2

- P0.5 Split parser strategies and capture live fixtures
- P1.1 Introduce provider-neutral LLM adapter

### Sprint 3

- P1.2 Refactor enrichment into registry/adapters
- P1.3 Add Unternehmensregister
- P1.4 Add OpenCorporates

### Sprint 4

- P1.5 Normalize source-claim storage
- P2.1 Tighten workflow typing
- P2.2 Improve MCP/application boundary

### Sprint 5

- P2.3 Build extraction/compliance eval set
- P3.1 Produce weekly issues and run user validation

## Definition Of Done For This Backlog

This backlog is complete when:

1. the full live path can run predictably
2. source expansion is modular
3. output quality is measured
4. user value is demonstrated

That is the point where the system stops being merely interesting and becomes a product.
