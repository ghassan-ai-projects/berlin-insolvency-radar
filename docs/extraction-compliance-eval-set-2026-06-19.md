# Extraction And Compliance Eval Set

**Date:** 2026-06-19
**Purpose:** Add a stable, fixture-backed quality harness for extraction/compliance changes

## Why This Exists

Runtime success is not enough. The pipeline also needs a small set of representative notices that make parser, extraction, and compliance changes measurable.

This eval set is intentionally small and cheap:

- it runs in unit-test time
- it does not require a live model
- it locks expected extraction payloads and compliance outcomes

## Corpus

Stored at:

- `tests/fixtures/evals/extraction_compliance_cases.json`

Current cases:

1. `corporate_gmbh_opening_order`
2. `corporate_se_case`
3. `sole_proprietor_rejected`

Each case includes:

- `raw_text`
- `source_url`
- `expected_extraction`
- `expected_compliance`

## Validation Path

The harness is:

- `tests/unit/test_extraction_eval.py`

It stubs the LLM response with the expected structured payload, then verifies:

1. extraction model parsing still accepts the payload shape
2. key extracted fields remain stable
3. deterministic compliance still returns the expected gate decision

## Value

This is not a substitute for live model evaluation. It is the minimum useful guardrail that prevents discussion-only regressions in extraction/compliance logic.

The next worthwhile expansion is:

- add 10-20 real anonymized notices from live fixtures
- record expected extraction deltas by field, not only pass/fail
- add false-positive and ambiguous legal-form cases
