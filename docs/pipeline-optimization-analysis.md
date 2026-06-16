# Pipeline Optimization Analysis

**Date:** 2026-06-16
**Based on:** Full codebase review after production hardening commit `b356a38`

---

## Summary

13 findings across 4 priorities. The 3 most impactful:

1. **CRITICAL — Risk review retry re-processes ALL candidates** (multiplicative cost amplifier)
2. **HIGH — Extraction node doesn't skip already-extracted candidates on retry**
3. **HIGH — Portal scraper re-fetches date windows already in the database**

---

## Finding #1 (CRITICAL): Risk Review Retry Loop Re-processes Every Candidate

**File:** `src/biradar/graph/pipeline_workflow.py` — `risk_review_node` + `review_router`

**What's wrong:** When any single candidate fails risk review, the router sends execution back to `extraction`. From there, the graph traverses `extraction → scoring → enrichment → risk_review` unconditionally. All non-quarantined candidates — including ones that already passed review (`status == "publish_ready"`) — are re-processed through ALL expensive stages.

**Waste:** For N candidates with 1 failing review, ~(2N+2) LLM calls instead of (N+1), plus ~(3N) extra HTTP enrichment calls. With DeepSeek API costs, this adds up multiplicatively.

**Fix:** Add guard clauses in `extraction_node`, `scoring_node`, and `enrichment_node` to skip candidates that already have results in `state`. Better: make the retry loop target `risk_review` directly instead of resetting all the way back to `extraction`.

---

## Finding #2 (HIGH): Portal Scraper Re-fetches Already-Scraped Date Windows

**File:** `src/biradar/sources/official_portal.py` — `fetch_date_range`

**What's wrong:** Every pipeline run hits the JSF portal for the full requested date range, even if previous runs already scraped the same window. `SourceRunRepository.get_latest_successful_run()` exists but is never called before fetching. The `upsert_raw_record` content-hash dedup prevents duplicate DB rows, but the HTTP request has already been made.

**Waste:** 30+ seconds per fetch, anti-bot risk, unnecessary load on a government portal.

**Fix:** Before fetching, query the latest successful source run. If it covers the requested range, skip. If partial overlap, narrow the window to only the uncovered portion.

---

## Finding #3 (HIGH): Extraction Node Does Not Guard Against Re-extraction

**File:** `src/biradar/graph/pipeline_workflow.py` — `extraction_node`

**What's wrong:** The node iterates all candidates and calls the LLM for any that are not quarantined. It never checks whether `state["extraction_results"]` already has a result for that `candidate_id`. On the retry loop from Finding #1, this causes needless re-extraction of every candidate.

**Fix:** Add `if candidate_id in state.get("extraction_results", {}): continue` at the top of the loop.

---

## Finding #4 (MEDIUM): Enrichment Results Discarded on Retry

**File:** `src/biradar/graph/pipeline_workflow.py` — `enrichment_node`

**What's wrong:** The node initializes a fresh empty `enrichment_results` dict every time. It never reads existing results from state. When the retry loop re-enters enrichment, previously-enriched candidates get re-enriched (HTTP calls wasted) and their first-pass data is wiped from state.

**Fix:** Initialize from existing state: `enrichment_results = dict(state.get("enrichment_results", {}))`. Add `if candidate_id in enrichment_results: continue`.

---

## Finding #5 (MEDIUM): `_persist_results` Re-computes Evidence Hashes on Every Run

**File:** `src/biradar/services/pipeline.py` — `_persist_results`

**What's wrong:** For all non-already-processed candidates, evidence hashes are recomputed and `insert_evidence` is called. The DB catches duplicates via `candidate_id + field + content_hash` lookup, but the hash computation and DB round-trip are still wasted for already-known evidence.

**Fix:** Pre-load existing evidence IDs in a batch query at the start of `_persist_results`.

---

## Finding #6 (MEDIUM): `_disabled_sources` Global State Leaks Across Pipeline Runs

**File:** `src/biradar/sources/enrichment.py` — module-level `_disabled_sources` set

**What's wrong:** Sources disabled in one pipeline run stay disabled for subsequent runs in the same process (e.g., server deployment, test harness). `_reset_disabled_sources()` exists but is only called from tests.

**Fix:** Clear `_disabled_sources` at the start of each `enrich_candidate()` call, or at pipeline start.

---

## Finding #7 (MEDIUM): Dead Config — `date_window_days` and `backfill_days_on_first_run`

**File:** `config/sources.yaml` — official_insolvency_berlin params

**What's wrong:** These parameters are defined but never read by any code. Date windows are caller-controlled (`pipeline-run --start-date/--end-date`). The config values suggest auto-window behavior that doesn't exist.

**Fix:** Either implement auto-window behavior or remove the dead params.

---

## Finding #8 (MEDIUM): No Test Coverage for Risk Review Retry Path

**File:** `tests/e2e/test_pipeline.py`

**What's wrong:** The stub risk reviewer always returns `passed_review=True`. The retry loop and router path are never exercised in tests.

**Fix:** Add a test with a stub that fails on first call and passes on second, asserting that extraction was not re-run for already-processed candidates.

---

## Low-Priority Findings

| # | File | Issue |
|---|------|-------|
| 9 | `agents/extraction.py`, `risk_review.py` | New `ChatOpenAI` per call → minor TLS overhead per invocation |
| 10 | `utils/prompts.py` | Greedy regex `\{.*\}` could match across multiple JSON objects |
| 11 | `storage/repository.py` | `upsert_candidate` always writes `updated_at` even when unchanged |
| 12 | `sources/official_portal.py` | Hardcoded 1.5s delay before every fetch, not configurable |
| 13 | `pipeline_workflow.py` | `enrichment_http_status` / `enrichment_blocked` check — dead code |
