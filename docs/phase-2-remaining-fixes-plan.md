# Phase 2 — Remaining Fixes Plan

**Date:** 2026-06-16
**Based on:** `berlin-insolvency-radar-analysis.md` handoff document
**Status:** In progress

---

## Fix #1: Remove unsupported `response_format` from DeepSeek calls

**Root cause:** DeepSeek V4 Flash does not support `response_format: json_object`. The API returns a 400 error: "This response_format type is unavailable now."

**Files affected:**
- `src/biradar/agents/extraction.py` line 49
- `src/biradar/agents/risk_review.py` line 60

**Fix:** Remove `model_kwargs={"response_format": {"type": "json_object"}}` from both `ChatOpenAI` constructors. The prompts already include a strict "Respond ONLY with a valid JSON object" instruction, and both files already have `robust_json_parse` fallback logic that handles markdown-wrapped JSON.

**Impact:** Fixes Problem #3 (pipeline never reaches publish-ready) because extraction will succeed and candidates will flow through to scoring/draft.

---

## Fix #2: Add `.env` loading to CLI entrypoint

**Root cause:** `DEEPSEEK_API_KEY` and other env vars are never loaded before CLI commands execute. The `python-dotenv` library is not a dependency.

**Files affected:**
- `src/biradar/cli/main.py`
- `pyproject.toml`

**Fix:**
1. Add `python-dotenv>=1.0.0` to `pyproject.toml` dependencies
2. At module level in `main.py`, load `.env` from `PROJECT_ROOT` before any downstream imports that read `os.environ`

```python
# Near top of main.py, before other biradar imports
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
```

---

## Fix #3: Pipeline never reaches publish-ready

**Root cause:** Cascading from Fix #1. When extraction LLM calls fail, all candidates are quarantined with `extraction_failed`. No candidates reach scoring or draft.

**Resolution:** Fix #1 resolves this. No additional code change needed.

---

## Fix #4: Harden enrichment — skip known-broken sources, detect anti-bot

**Root cause:** `handelsregister.de` returns HTTP 400 on every request (the search endpoint likely requires POST or JSF session state). Company websites frequently hit SSL errors. Retries × 4 sources × 67 candidates make enrichment very slow.

**Files affected:**
- `src/biradar/sources/enrichment.py`

**Fix:**
1. Mark `handelsregister.de` as a known-broken source with a health-check flag. On first 400, disable it for the rest of the pipeline run.
2. Detect HTTP 403 / Cloudflare challenges and mark as `blocked_by_anti_bot` per architecture rules.
3. Reduce per-source timeout from config default (10s) to 5s for handelsregister specifically.

**Implementation approach:**
- Add a module-level `_disabled_sources: set[str]` that tracks sources that returned terminal errors (400, 403)
- Check this set in `enrich_candidate()` before calling each source
- When handelsregister returns 400, add it to `_disabled_sources` and log once

---

## Fix #5: Round computed_score to 2dp in issue draft + export display

**Root cause:** DuckDB stores `computed_score` as FLOAT, causing floating-point artifacts like `3.0999999046325684` instead of `3.10`.

**Files affected:**
- `src/biradar/services/issues.py` — line ~163: `f"- **Opportunity Score:** {score['computed_score']}"`
- `src/biradar/output/export.py` — line ~75: `f"- **Radar Score:** {computed_score} ({category})"`

**Fix:** Format with `:.2f` in f-strings where scores are displayed. The scoring engine already calls `round(score, 2)` but that doesn't prevent FLOAT storage artifacts in DuckDB.

---

## Fix #6: Cron readiness

**Status:** Not a code fix — operational configuration.

**Notes for scheduling:**
- The `pipeline-run` command should be invoked with `--start-date` 7 days back and `--end-date` today
- Cron entry: `0 8 * * 1 cd ~/my-projects/berlin-insolvency-radar && uv run biradar pipeline-run --start-date $(date -v-7d +%Y-%m-%d) --end-date $(date +%Y-%m-%d)`
- After Fix #1–#5 are applied, the pipeline will run fully unattended
- Consider adding `--thread-id "cron_$(date +%Y%m%d)"` for distinct checkpoint threads

---

## Verification

After all fixes applied:
1. `uv run biradar pipeline-check` — fixture-backed deterministic test (72 existing tests)
2. `uv run pytest -m "not live"` — all non-live tests
3. Manual live test: `uv run biradar pipeline-run --start-date 2026-06-14 --end-date 2026-06-16` with a valid `.env` DeepSeek key
