# Operationalization Plan

**Date:** 2026-06-19
**Goal:** Turn Berlin Insolvency Radar from a locally validated prototype into a dependable live operational system

## Current Reality

As of 2026-06-19:

- local non-live validation mostly works
- live portal acquisition works at least once
- full live end-to-end does not yet run reliably because the extraction/model stage timed out
- repo quality gate is not fully green because `make check` currently fails at formatting

So the job is not "build more features". The job is:

1. make the live path reliable
2. make failures diagnosable
3. make components replaceable
4. prove output quality and user value
5. broaden the data base without turning the codebase into source spaghetti

## Operational Target

The system is operational when all of these are true:

1. A scheduled live run completes without manual intervention.
2. Failures are classified by stage: acquisition, extraction, enrichment, review, export.
3. Portal-only and full-live smoke checks exist and are separately runnable.
4. One provider timeout does not make the system opaque.
5. At least one labeled eval exists for extraction/compliance quality.
6. The repo’s own `make check` passes.
7. At least one additional official or provenance-rich source is integrated through the new adapter architecture.

## Phase 1: Stabilize The Live Path

**Objective:** Prove that the live pipeline can run predictably and that failures are isolated.

### Work

1. Split runtime modes into three explicit paths:
   - `portal-only`
   - `portal-with-stubs`
   - `full-live`
2. Add stage-level timing and status recording for:
   - fetch
   - parse
   - extract
   - score
   - enrich
   - review
   - export
3. Add explicit timeout and retry policy for model calls.
4. Add a hard cap on records for live smoke runs.
5. Make `make check` green again.

### Why First

The live validation already showed that the portal path can work and that the model path is the first operational bottleneck. Until runtime modes and stage diagnostics exist, every live failure is more expensive to debug than it should be.

### Exit Criteria

- `make check` passes
- `uv run biradar live-smoke-portal` succeeds on a recent date window
- `uv run biradar live-smoke-full --max-records 3` either succeeds or fails with a stage-specific error
- run output clearly states where time was spent and where it failed

## Phase 2: Fix Parser Architecture

**Objective:** Make portal parsing robust to markup variation.

### Work

1. Split `fetch` and `parse` concerns in [`src/biradar/sources/official_portal.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/sources/official_portal.py:1).
2. Introduce parser strategies:
   - HTML table parser
   - JSF partial-response parser
   - span/div result parser
   - portal error parser
3. Capture fresh dated live fixtures from the current portal.
4. Add tests for:
   - too many results
   - search form returned without results
   - empty successful response versus classified failure

### Why Second

The portal is the system’s entry point. If it changes shape, everything downstream becomes noise. Right now the parser is too dependent on one DOM structure.

### Exit Criteria

- at least 3 current live response fixtures exist
- parser tests cover every known response type
- zero-record outcomes are classified as:
  - no matches
  - too many matches
  - parser mismatch
  - blocked or invalid form response

## Phase 3: Decouple The LLM Layer

**Objective:** Make provider switching and operational fallback practical.

### Work

1. Add a provider-neutral interface such as `StructuredLLM`.
2. Move provider construction into DI/config.
3. Implement a provider factory with current DeepSeek support.
4. Add one alternate provider path or a mock/local adapter.
5. Enforce structured JSON responses in one place, not separately in each agent.

### Why Third

The live failure happened in the model stage. This does not automatically mean “leave DeepSeek,” but it does mean the system should not be tightly coupled to one provider implementation.

### Exit Criteria

- extraction and review no longer construct `ChatOpenAI` directly
- provider/model choice is config-driven
- one provider can be replaced without changing extraction/review business logic
- model timeout and retry behavior is centralized

## Phase 4: Redesign Enrichment As A Source Registry

**Objective:** Make enrichment extensible without turning one file into a maintenance trap.

### Work

1. Split [`src/biradar/sources/enrichment.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/sources/enrichment.py:1) into:
   - `models.py`
   - `orchestrator.py`
   - `registry.py`
   - one file per source
2. Define normalized source claim objects.
3. Aggregate claims by field precedence rather than by source-name `if` chains.
4. Support config-driven source enable/disable without code edits.
5. Persist source claims, not only merged enrichment fields.
6. Prepare the architecture for adding:
   - `unternehmensregister`
   - `opencorporates`
   - future `handelsregister` and `bris` adapters in the same shape

### Why Fourth

The current enrichment works for a few sources, but it will get worse every time you add another adapter. This should be fixed before source count grows.

### Exit Criteria

- adding a new source requires adding one module and one registry entry
- source adapters return normalized claims
- aggregation is claim-based, not source-name-based
- per-source tests exist

## Phase 5: Expand The Source Base

**Objective:** Improve coverage, corroboration, and company context through modular additional sources.

### Work

1. Add `Unternehmensregister` as the first new official source.
   - Use it as secondary acquisition and official enrichment/corroboration.
2. Add `OpenCorporates` as the first low-friction normalization source.
   - Use it for company matching, identifier normalization, and provenance-rich enrichment.
3. Move current `Handelsregister` logic into the new adapter architecture.
4. Add `BRIS` only as a targeted fallback for cross-border identity resolution.
5. Update `config/sources.yaml` to support:
   - source role
   - trust level
   - priority
   - enable/disable
   - source-specific params

### Why Fifth

The product will be stronger and more defensible if it is not dependent on a single brittle acquisition path and weak ad hoc enrichment. But source expansion should happen only after the adapter architecture exists, otherwise the code quality will regress as the data base grows.

### Exit Criteria

- `Unternehmensregister` is integrated through the new adapter shape
- `OpenCorporates` is integrated through the new adapter shape
- current `Handelsregister` integration no longer lives as special-case logic in one large file
- source config supports multiple acquisition and enrichment sources cleanly
- one new source can be added without editing a central monolith
## Phase 6: Strengthen Storage And Workflow Contracts

**Objective:** Reduce silent drift and make runs inspectable after the fact.

### Work

1. Replace generic workflow dict payloads with typed models where practical.
2. Normalize storage for source claims/evidence lineage.
3. Add explicit run metadata tables or audit summaries for stage outcomes.
4. Tighten checkpoint expectations:
   - SQLite saver available in target environment
   - documented fallback behavior when unavailable

### Why Sixth

This is less urgent than live reliability, but it matters for long-term maintainability and operator trust.

### Exit Criteria

- workflow state is less ad hoc
- source claim lineage is queryable
- checkpoint capability is either fully supported or explicitly downgraded

## Phase 7: Prove Output Quality

**Objective:** Show that the system is not only runnable, but trustworthy.

### Work

1. Build a labeled sample of recent Berlin filings.
2. Measure:
   - extraction field accuracy
   - compliance precision/recall
   - publish-ready yield
3. Record error categories from live runs over multiple windows.
4. Compare ranked output against manual review.

### Why Seventh

An operational pipeline that produces low-quality output is still not a product.

### Exit Criteria

- labeled eval set exists
- extraction/compliance metrics are recorded in `docs/`
- at least one weekly run can be reviewed against manual expectations

## Phase 8: Prove Product Value

**Objective:** Validate that the output is worth using and potentially worth paying for.

### Work

1. Produce 3 to 4 real weekly issues.
2. Have target users review them.
3. Capture:
   - usefulness
   - novelty
   - actionability
   - willingness to read regularly
4. Decide whether the product is best framed as:
   - analyst tool
   - newsletter
   - alerting system
   - data feed

### Why Last

You first need stable live operation and trustworthy output. Then you can test whether the format and product framing are correct.

### Exit Criteria

- at least 3 target users have reviewed real issues
- product direction is chosen based on evidence, not assumption

## Recommended Build Order

If speed matters, do it in this order:

1. Green the repo and add live runtime modes
2. Add stage-level observability
3. Harden model timeout/failure handling
4. Refactor parser strategy layer
5. Decouple provider construction
6. Modularize enrichment
7. Add `Unternehmensregister` and `OpenCorporates`
8. Improve storage/workflow contracts
9. Run evals
10. Run user validation

## What Not To Do

Avoid these until the earlier phases are done:

- adding many more enrichment sources before the adapter architecture exists
- adding external publishing
- adding scheduling/cron in production
- adding more LLM complexity
- redesigning the UI/export format extensively

Those can all wait. The live operational core cannot.

## Next 7-Day Execution Plan

If the goal is immediate progress, the next week should look like this:

### Day 1

- make `make check` pass
- add a doc-tracked live smoke procedure

### Day 2

- add `portal-only` and `portal-with-stubs` runtime modes
- add stage timing logs

### Day 3

- add model timeout, retry, and error classification
- rerun full live smoke with exact dates

### Day 4

- refactor parser into strategies
- capture fresh live fixtures

### Day 5

- add parser regression tests
- verify recent live date windows again

### Day 6

- add provider abstraction layer
- keep DeepSeek as default, but remove direct construction from agents

### Day 7

- scaffold the source registry structure
- add the `Unternehmensregister` integration design and `OpenCorporates` adapter stub

### Day 8

- implement `Unternehmensregister` and `OpenCorporates` adapters
- move existing enrichment sources into the new adapter shape

### Day 9

- write first labeled eval set
- record metrics and decide whether output quality is good enough to continue

## Bottom Line

To make this operational, the system needs less product ambition and more runtime discipline.

The shortest path is:

- stabilize live execution
- isolate parser and model failures
- make provider and source/enrichment seams modular
- add better official and provenance-rich data sources
- prove output quality

That is the path from prototype to dependable system.
