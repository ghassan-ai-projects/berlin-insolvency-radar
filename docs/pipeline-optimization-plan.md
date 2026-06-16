# Pipeline Optimization — Implementation Plan

**Based on:** `docs/pipeline-optimization-analysis.md`
**Principle:** Think → Plan → Do. One fix at a time.

---

## Fix Order & Dependency

```
Fix 1 (CRITICAL) ──┐
Fix 2 (HIGH)     ──┤── independent, can be done in any order
Fix 3 (MEDIUM)   ──┤
Fix 4 (MEDIUM)   ──┤
Fix 5 (MEDIUM)   ──┘── depends on Fix 1 (tests the new guards)
```

---

## Fix 1: Guard Nodes Against Re-processing on Retry

**Root cause:** `risk_review_node` sets `current_step = "extraction"` on retry. The router sends execution back to `extraction`, which unconditionally processes all non-quarantined candidates through the full chain.

**Plan:**
1. `extraction_node` — before LLM call, `if candidate_id in state["extraction_results"]: continue`
2. `scoring_node` — before scoring, `if candidate_id in scores and scores[candidate_id].get("status") == "approved": continue`
3. `enrichment_node` — init `enrichment_results = dict(state.get("enrichment_results", {}))`. Before enrichment call, `if candidate_id in enrichment_results: continue`

**Files:** `src/biradar/graph/pipeline_workflow.py` only
**Risk:** Low — additive guards, no behavior change for first-pass candidates
**Test:** Existing tests pass. Fix 5 will validate the retry path.

---

## Fix 2: Portal Scraper Date Window Check

**Root cause:** `fetch_date_range` always hits the live portal, even for date windows already scraped.

**Plan:**
1. In `run_pipeline`, before calling `fetch_date_range`, query `SourceRunRepository` for the latest successful run covering the requested source
2. If a run exists whose `start_date <= requested_start AND end_date >= requested_end`, skip fetch, return cached records from `raw_records` table
3. If partial overlap, adjust `start_date`/`end_date` to only the uncovered portion

**Files:** `src/biradar/services/pipeline.py`, `src/biradar/sources/official_portal.py`, `src/biradar/storage/repository.py`
**Risk:** Medium — changes to scraping logic. Need to verify with both fixture and live modes.
**Test:** `pipeline-check` runs twice on same DB (already tests idempotency). Add assertion that second run hits 0 new raw records.

---

## Fix 3: Evidence Hash Batch Pre-load

**Root cause:** `_persist_results` recomputes SHA-256 hashes and calls `insert_evidence` for every candidate, even when evidence rows already exist.

**Plan:**
1. Collect all `(candidate_id, field)` pairs that would be inserted
2. Batch `SELECT candidate_id, field FROM evidence WHERE (candidate_id, field) IN (...)`
3. Skip hash computation and insert for pairs that already exist

**Files:** `src/biradar/services/pipeline.py`, `src/biradar/storage/repository.py`
**Risk:** Low — additive optimization
**Test:** `pipeline-check` runs twice, verify evidence count stays stable.

---

## Fix 4: `_disabled_sources` Lifecycle

**Root cause:** Module-level `set` persists across pipeline runs in the same process.

**Plan:**
1. Call `_reset_disabled_sources()` at the start of `run_pipeline()` (production path)
2. Or: clear at the start of each `enrich_candidate()` call (safer, per-candidate isolation)

**Files:** `src/biradar/sources/enrichment.py`, `src/biradar/services/pipeline.py`
**Risk:** Low
**Test:** Add unit test: enrich candidate → disable source → enrich another candidate → assert source is re-enabled.

---

## Fix 5: Test for Risk Review Retry Path

**Root cause:** No test exercises the `needs_retry` → `extraction` loop path.

**Plan:**
1. Create a stub risk reviewer that fails on first call, passes on second (per candidate)
2. Run pipeline with 2 candidates, 1 failing review initially
3. Assert: 2 extractions total (not 3+), both candidates reach publish_ready

**Files:** `tests/e2e/test_pipeline.py`
**Risk:** Low
**Depends on:** Fix 1 (guards must be in place for assertion to hold)

---

## Low-Priority (Deferred)

- #9 LLM client reuse — micro-optimization, <200ms per run
- #10 Greedy JSON regex — rarely triggers, existing fallback works
- #11 `upsert_candidate` unconditional write — negligible DuckDB overhead
- #12 Hardcoded 1.5s delay — config-driven later
- #13 Dead `enrichment_http_status` check — cosmetic cleanup
- #7 Dead config params — cleanup, no operational impact
