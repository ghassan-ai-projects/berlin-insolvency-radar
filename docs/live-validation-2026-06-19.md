# Live Validation

**Date:** 2026-06-19
**Reviewer:** Codex
**Scope:** One real live validation attempt against the official portal and current LLM path, plus one narrower live portal isolation run

## Summary

Two live validations were run for the date window **2026-06-17** through **2026-06-19**.

Result:

- the **full live pipeline** did **not** complete successfully
- the **live portal acquisition path** **did** complete successfully when extraction, review, and enrichment were stubbed
- newly added **North Data** and **Wikidata** enrichment adapters both returned real data for `Zalando SE`
- the final `portal_only` smoke command completed successfully after the architecture changes

This means the repo now has a real live verification result, and the current bottleneck is more likely the live model/API stage than the official portal fetch itself.

## Run 1: Full Live E2E

Command:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/e2e/test_live_pipeline.py -m live -v
```

Outcome:

- **Failed**
- failure type: `pytest-timeout`
- elapsed time: about **61.78 seconds**

Observed behavior:

- the test did not fail immediately on missing config
- the pipeline progressed into the real workflow
- the failure occurred during the live extraction call in [`src/biradar/agents/extraction.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/extraction.py:63)
- stack trace shows the timeout occurred while waiting on the live chat completion response over HTTPS

Interpretation:

- this is a real live failure, not a fake pass
- the portal path appears to have advanced far enough to reach extraction
- the current full live runtime is not reliable enough yet for end-to-end use

## Run 2: Live Portal Isolation With Stubbed LLM/Enrichment

Command shape:

- `run_pipeline(...)`
- live source mode
- real portal acquisition
- stubbed extractor
- stubbed risk reviewer
- stubbed enricher

Outcome:

- **Succeeded**
- final state: `completed`
- issue export produced successfully

Recorded result summary:

- `source_runs`: 1
- `scheduled_runs`: 1
- `raw_records`: 303
- `candidates`: 3
- `publish_ready`: 1
- latest source run row:
  - status: `completed`
  - `records_seen`: 438
  - `records_imported`: 438
  - `error_json`: `None`

Interpretation:

- the official portal fetch path did return real data
- the parser and acquisition path were operational enough to persist hundreds of raw records in this live run
- the system can complete end-to-end on live source data when downstream LLM-dependent steps are replaced with deterministic stubs

## Run 3: Live Enrichment Adapter Check

Command:

```bash
uv run python -c 'from biradar.sources.enrichment import lookup_north_data, lookup_wikidata; print("NORTH_DATA", lookup_north_data("Zalando SE")); print("WIKIDATA", lookup_wikidata("Zalando SE"))'
```

Outcome:

- **Succeeded**
- `lookup_north_data("Zalando SE")` returned:
  - registry number: `HRB 158855 B`
  - sector: `Vermittlungstätigkeiten für den Einzelhandel ohne ausgeprägten Schwerpunkt`
- `lookup_wikidata("Zalando SE")` returned:
  - website: `https://www.zalando.de/`
  - sector: `Einzelhandel`

Interpretation:

- the new enrichment registry is not only unit-tested; at least two newly added adapters returned live production data on **2026-06-19**
- the source-expansion direction is operational, not theoretical

## Run 4: Final Live Portal Smoke After Refactor

Command:

```bash
uv run biradar live-smoke-portal --start-date 2026-06-17 --end-date 2026-06-19 --max-records 5
```

Outcome:

- **Succeeded**
- final state: `fetched`
- fetch duration: about **3.174 seconds**
- records returned by the live portal fetch: **438**
- source run ID: `631e6ac8-3499-4b2e-b919-59e3a37ac761`

Interpretation:

- the official portal path still works after the parser and runtime refactors
- the post-refactor codebase retains a working live acquisition path, not just historical evidence from an earlier intermediate state

## What This Proves

It is now reasonable to say all of the following:

- the repo has been tested against the **real official portal** at least once on **2026-06-19**
- the live portal path is not purely hypothetical
- the full live product path is still blocked by reliability issues in the model-dependent stage

It is not yet reasonable to say:

- the full live production workflow is reliable
- the current model path is production-ready
- end-to-end latency is operationally acceptable

## Most Important Design Implications

### 1. The acquisition layer and LLM layer need separate operational contracts

Right now one timeout in extraction makes the whole live pipeline look broken, even when the live portal fetch worked. The system needs clearer stage-level status and operator reporting.

### 2. Live extraction needs stronger timeout and fallback behavior

The current extraction path waits on a synchronous model call with no explicit stage-level timeout, circuit breaker, or fallback mode. That is the first operational weakness exposed by the live run.

### 3. The repo needs a dedicated live smoke command

There should be an explicit CLI or test mode for:

- portal only
- portal + stubbed downstream
- full live end-to-end

That would make failures diagnosable much faster.

## Other Design Areas That Still Need Improvement

Beyond parser robustness, model abstraction, and generic enrichment, these areas still need work:

### Operational observability

- stage-level timing is weak
- there is no explicit run report for `fetch`, `extract`, `score`, `review`, and `export`
- failures are visible, but not summarized in an operator-friendly way

### Workflow state typing

[`src/biradar/graph/state.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/state.py:41) still carries many generic `dict` payloads. That is flexible, but it makes the pipeline easier to break quietly as fields evolve.

### MCP boundary quality

[`src/biradar/mcp/server.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/mcp/server.py:246) is a workable dispatcher, but not yet a strong application boundary. Workflow execution, transport concerns, and envelope shaping are still fairly close together.

### Storage model for source claims

[`src/biradar/storage/db.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/storage/db.py:206) has a flat `enrichments` table, while real enrichment is already moving toward multi-source claims. The persistence model should evolve toward normalized source claims and source evidence, not only merged enrichment fields.

### Human-review model

[`src/biradar/services/reviews.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/services/reviews.py:29) is clean for manual candidate review, but the repo is now mixing:

- manual editorial review concepts
- fully agentic workflow concepts
- automatic publish-ready transitions

That boundary needs to become more explicit.

## Bottom Line

The live test answered the key question.

- **Yes**, the project has now been live-tested against real data at least once.
- **No**, the current full live path is not yet reliable enough.
- The first confirmed operational bottleneck is the **model-dependent extraction stage**, not the existence of a live portal path.
