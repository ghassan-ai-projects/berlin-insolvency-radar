# Full Project Review

**Date:** 2026-06-19
**Reviewer:** Codex
**Scope:** End-to-end repository review, local validation status, product-value validation status, and improvement recommendations

## Executive Verdict

Berlin Insolvency Radar is a credible engineering prototype with a strong repository structure, a coherent local workflow, and meaningful non-live test coverage. It is not yet convincingly validated as a real product.

The main reason is not code style or architecture. The main reason is that the repository currently proves the fixture-backed path much better than it proves the live market path. The local pipeline works. The commercial thesis is still mostly argued, not demonstrated.

## What Is Good

- The 6-layer architecture is real, not just documented. The boundaries between `domain/`, `storage/`, `services/`, `graph/`, and `mcp/` are mostly clear.
- Deterministic logic is placed in pure modules where it belongs, especially `domain/compliance.py`, `domain/dedupe.py`, `domain/scoring.py`, and `domain/statuses.py`.
- SQL is centralized in [`src/biradar/storage/repository.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/storage/repository.py:1), which keeps persistence concerns isolated.
- The pipeline has a real end-to-end shape: acquisition, extraction, enrichment, scoring, review, export, and persistence.
- The repo contains acceptance and E2E tests instead of only unit tests, which is the right instinct for this kind of system.
- The product positioning is sharper than most early-stage data projects. A curated Berlin insolvency signal is a more focused idea than a general-purpose scraping platform.

## What I Validated

### Repository Checks

These commands were run locally in this review:

```bash
make check
make lint
make typecheck
make test
make test-acceptance
make test-e2e
UV_CACHE_DIR=.uv-cache uv run biradar pipeline-check
```

### Actual Outcomes

- `make check` failed immediately at `format-check`.
  - Ruff reported unformatted tracked files:
    - [`src/biradar/agents/extraction.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/extraction.py:1)
    - [`src/biradar/agents/risk_review.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/risk_review.py:1)
    - [`src/biradar/graph/pipeline_workflow.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/pipeline_workflow.py:1)
- `make lint` passed.
- `make typecheck` passed with `0 errors, 0 warnings, 0 informations`.
- `make test` passed with `48 passed`.
- `make test-acceptance` passed with `20 passed`.
- `make test-e2e` passed with `6 passed, 1 deselected`.
- `uv run biradar pipeline-check` passed twice and produced export artifacts.

### Important Validation Limits

- The strongest proof is fixture-backed, not live.
- I did not run the live test in [`tests/e2e/test_live_pipeline.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/e2e/test_live_pipeline.py:1) because it requires real network access and a real `DEEPSEEK_API_KEY`.
- `pipeline-check` emitted `SQLite LangGraph checkpoint saver unavailable; using in-memory saver`, so resumable checkpointing was not proven in this environment even though the repo documents it as a feature.

## Main Findings

### 1. The product is locally validated, but the live acquisition path is still the biggest risk

The scraper/parser path still looks fragile against the real portal.

The parser in [`src/biradar/sources/official_portal.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/sources/official_portal.py:371) is built around finding a `table` with `id="tbl_ergebnis"` and extracting `tr`/`td` cells. The fixture reinforces that assumption: [`tests/fixtures/official_portal/sample_response.html`](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/fixtures/official_portal/sample_response.html:1) explicitly says it is a full HTML page with `tbl_ergebnis`.

But the repo also contains a current investigation note in [`docs/issue-parsing.md`](/Users/ghassan/my-projects/berlin-insolvency-radar/docs/issue-parsing.md:17) stating that the modern live portal returned span-based `tbl_ergebnis:NNN:otx_*` entries rather than the old table structure.

If that note is still accurate, then the repo’s best-tested path is anchored to an outdated portal shape. That means the highest-value claim of the product, reliable live acquisition, is not yet proven.

### 2. The repo overstates checkpoint/resume confidence relative to what was validated

The README and architecture docs present `data/checkpoints.sqlite` resumability as part of the system. In this environment, the code fell back to in-memory checkpointing:

- Implementation: [`src/biradar/graph/checkpoints.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/graph/checkpoints.py:20)
- Runtime evidence: `pipeline-check` logged `SQLite LangGraph checkpoint saver unavailable; using in-memory saver`

This does not mean the pipeline is broken. It does mean crash-resume behavior is not currently validated here, and some docs describe a stronger guarantee than the current environment proved.

### 3. The LLM path is operational, but not hardened enough for a commercial intelligence product

Both LLM wrappers rely on prompt discipline and post-hoc parsing:

- [`src/biradar/agents/extraction.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/extraction.py:42)
- [`src/biradar/agents/risk_review.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/risk_review.py:53)

What is missing:

- No `model_kwargs={"response_format": {"type": "json_object"}}` on the model calls.
- Extraction failure collapses to `ExtractionResult(is_consumer_likely=True)`, which is safe but can quietly suppress valid opportunities.
- Risk review returns internal exception text inside rejection reasons, which is acceptable for debugging but weak for a production-facing contract.

This is good enough for a prototype. It is weak for proving recall, consistency, and analyst trust.

### 4. The top-level repo health signal is red even though most validation passes

Right now the honest status is:

- functional local path: mostly green
- repo gate: red

That matters because a repo whose own `make check` fails is hard to call finished. The failure is simple formatting drift, but it still means the published “green path” is not actually green today.

### 5. The value case is still thesis-heavy and evidence-light

The research docs are directionally good:

- [`docs/research/market.md`](/Users/ghassan/my-projects/berlin-insolvency-radar/docs/research/market.md:1)
- [`docs/research/business-model.md`](/Users/ghassan/my-projects/berlin-insolvency-radar/docs/research/business-model.md:1)

They support why the niche could matter. They do not yet validate that this implementation produces differentiated, decision-useful intelligence.

What is missing is not more market prose. What is missing is product evidence:

- precision of corporate-only filtering on recent live filings
- precision of extraction on a labeled sample
- number of publishable candidates per week
- analyst time saved versus manual review
- whether the ranking actually separates interesting opportunities from noise
- whether any real target user would pay for the export as it exists now

## Why You May Still Be Unhappy With The Result

The repo is optimized around building a correct-looking pipeline, not around proving that the output is valuable.

That creates a common failure mode:

- the architecture feels serious
- the tests feel reassuring
- the export exists
- but the final artifact is not yet obviously something a buyer would want every week

In other words, the project currently answers "can this be built?" better than it answers "does this materially outperform manual monitoring or cheaper alternatives?"

## Recommended Improvement Plan

### Priority 0: Prove the live portal path

This is the first thing to fix because every downstream claim depends on it.

1. Capture fresh live HTML/XML response fixtures from the current portal for exact dates.
2. Add parser support for the modern result DOM if the portal no longer returns `tbl_ergebnis` tables.
3. Add a regression fixture for the "too many hits" response so zero records is not treated as a quiet success.
4. Add one explicit live smoke procedure with a fixed small date window and record the outcome in `docs/`.

Target files:

- [`src/biradar/sources/official_portal.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/sources/official_portal.py:1)
- [`tests/unit/test_official_portal.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/unit/test_official_portal.py:1)
- [`tests/fixtures/official_portal/sample_response.html`](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/fixtures/official_portal/sample_response.html:1)

### Priority 1: Replace "it runs" validation with "it is trustworthy" validation

Add a scored evaluation set of real notices.

Recommended minimum:

1. Build a 50-notice labeled set from recent Berlin filings.
2. Record expected fields: company name, legal form, court, case number, filing date, proceeding stage, consumer/corporate label.
3. Measure extraction accuracy field by field.
4. Measure compliance false positives and false negatives.
5. Measure how many notices become `publish_ready` after review.

Without this, you cannot defend the output quality.

### Priority 2: Validate actual user value, not only technical completion

Run a lightweight operator trial.

Recommended test:

1. Produce 4 weekly issues from live or recent historical data.
2. Have 3 to 5 target users score each issue on usefulness, novelty, and actionability.
3. Record whether they would have discovered the candidate anyway.
4. Record whether the score/ranking changed what they would prioritize.
5. Use that to decide whether the product is a newsletter, alert tool, analyst workbench, or lead-generation feed.

This will probably teach you more than another round of refactoring.

### Priority 3: Tighten the LLM contract

1. Use structured JSON response mode in both LLM wrappers.
2. Separate "LLM failed" from "consumer likely" so safe fallback does not hide recall loss.
3. Keep internal exception details in logs, not user-facing payloads.
4. Add seed-eval fixtures for adversarial and malformed notices.

Target files:

- [`src/biradar/agents/extraction.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/extraction.py:28)
- [`src/biradar/agents/risk_review.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/risk_review.py:34)

### Priority 4: Make the documented "green path" actually green

1. Run `make format` and restore `make check` to passing.
2. Add a short validation status document that distinguishes:
   - fixture-backed validated
   - live validated
   - commercial-value validated
3. Stop using "production-ready" language until the live path and buyer value are both demonstrated.

### Priority 5: Improve the deliverable, not just the pipeline

The export is structurally fine, but it is still closer to an internal report than a product someone would pay for.

Focus the issue artifact on:

- why this candidate matters now
- what is known versus inferred
- immediate next action for the reader
- confidence and evidence density
- what makes this better than reading the portal directly

The strongest likely improvement is editorial compression, not more fields.

Target file:

- [`src/biradar/output/export.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/output/export.py:21)

## Suggested Success Criteria For The Next Iteration

I would not call the project truly successful until all of these are true:

1. `make check` passes cleanly.
2. A current live portal smoke test passes on a recorded date range.
3. The parser is validated against current live markup, not only historical fixtures.
4. Checkpoint/resume is either proven in the current environment or explicitly downgraded in docs.
5. A labeled extraction/compliance eval exists with published metrics.
6. At least 3 target users review real issues and confirm they would pay attention to the output.
7. The weekly export reads like a decision product, not only a system artifact.

## Bottom Line

This repo is better than a toy and worse than a validated product.

The engineering base is good enough to continue from. The current weakness is not that the code is chaotic. The weakness is that the project still lacks decisive evidence on two things:

- does the live acquisition path work reliably against the current portal
- does the produced intelligence create enough user value to justify the product

Those should be the next proving steps. Not a broad rewrite.
