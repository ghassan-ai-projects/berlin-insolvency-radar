# Berlin Insolvency Radar — Analysis & Handoff

## What Was Done

### 1. Clone & Setup
- Cloned `ghassan-ai-projects/berlin-insolvency-radar` to `data` machine at `~/my-projects/berlin-insolvency-radar/`
- Installed `uv`, synced deps (Python 3.12, DuckDB, LangGraph, MCP, httpx, etc.)
- Copied legacy research from orch (`legacy-research/`)
- Configured `.env` with DeepSeek API key

### 2. Legacy Data
- Found `insolvency_scout.duckdb` (4.8MB, 311 filings) on orch at `~/my-projects/insolvency-scout/data/`
- Created bridge script (`scripts/import-legacy-scout.py`) to convert legacy schema to biradar-compatible format
- Imported successfully: 311 raw records → 63 distinct corporate candidates
- Cleaned up legacy DB copies

### 3. MCP Full Cycle (all via MCP tools)
- `radar_health` — 63 candidates loaded
- `radar_list_candidates` — list of review_ready candidates
- `radar_review_candidate` — approved 3 (Spark Networks GmbH, BrewDog Retail Germany GmbH, Brewdog GmbH)
- `radar_create_issue_draft` — scored newsletter draft created
- `radar_export_issue` — exported to `data/exports/issue-2026-W25-free.md`
- Scored output: Spark Networks 3.10 (Hot), BrewDog entities 2.70-2.90 (Solid)

### 4. Live Portal Scraping
- The scraper at `src/biradar/sources/official_portal.py` successfully connects to `neu.insolvenzbekanntmachungen.de` (JSF portal)
- Tested: returns HTML with 250+ records/day for Berlin
- Fields in the HTML table (`tbl_ergebnis`):
  ```
  [0] publication_date (dd.MM.yyyy)
  [1] case_number (e.g. 36a IN 4312/24)
  [2] court (e.g. Charlottenburg (Berlin))
  [3] company/person name
  [4] seat/city
  [5] register number (e.g. Berlin, HRB 229975)
  [6] detail form button (empty text)
  ```

### 5. Parsing Fix Applied
- **File:** `src/biradar/sources/official_portal.py`
- **Method:** `_extract_records_from_table`
- **Problem:** Old code used `cells[0]` as company_name and `cells[3]` as pub_date — wrong order
- **Fix:** Reordered to correct column mapping, added `register_number` field
- **Also:** `_parse_html_results` now targets `tbl_ergebnis` by ID instead of iterating all tables
- **Verification:** 251 records parsed correctly from live portal (67 corporate, 184 consumer)

---

## Remaining Problems for Coding Agent

### Problem 1: DeepSeek `response_format: json_object` is unsupported
**Files:** `src/biradar/agents/extraction.py` (line 49), `src/biradar/agents/risk_review.py` (line 60)
- Both use `model_kwargs={"response_format": {"type": "json_object"}}`
- The API returns: `"This response_format type is unavailable now"` (400 error)
- The model is `deepseek-v4-flash` (confirmed via API: available models are `deepseek-v4-flash` and `deepseek-v4-pro`)
- **Fix:** Remove or replace `response_format` with a prompt-level JSON instruction instead. DeepSeek V4 Flash doesn't support structured output natively.

### Problem 2: Env vars never loaded before CLI commands
**File:** `src/biradar/cli/main.py`
- **Fix applied:** Added manual `.env` parser at module level that reads PROJECT_ROOT/.env and sets `os.environ.setdefault()`
- This is a **newly written fix** that needs review — it reads the `.env` file line by line instead of using `python-dotenv` (which isn't a dependency)
- Alternative: add `python-dotenv` to deps and use `load_dotenv()`

### Problem 3: Pipeline-run never reaches publish-ready (all candidates quarantined)
**Root cause chain:**
1. Portal scraper returns 250+ records correctly ✅
2. `normalize_and_compliance_node` correctly filters corporate vs consumer ✅
3. `extraction_node` calls DeepSeek LLM → fails with `response_format` error → all candidates marked `quarantined` with `extraction_failed` reason
4. Since everything is quarantined, no candidates reach scoring or draft

**Fix needed:** Either (a) fix DeepSeek structured output, or (b) make extraction_node non-fatal when LLM fails (graceful degradation)

### Problem 4: Enrichment step is slow and fragile
**File:** `src/biradar/sources/enrichment.py`
- Hits handelsregister.de (returns 400), company websites (SSL errors), etc.
- Retries 3x per source per candidate × 67+ candidates = very slow
- Times out the 90s pipeline window

### Problem 5: Floating point precision in issue draft
**File:** `src/biradar/services/issues.py`
- `computed_score` stored as DuckDB FLOAT → outputs `3.0999999046325684` instead of `3.10`
- Minor cosmetic issue, but affects newsletter readability

### Problem 6: Cron job needs smarter pipeline
- Currently registered as isolated cron at 08:00 Berlin daily
- The cron command needs to handle the extraction/enrichment issues above
- Currently set to run `pipeline-run` with a 7-day lookback

---

## Architecture Decisions

- **Layer rule:** `cli/ → mcp/ → services/ → graph/ → agents/ → domain/`
- **All SQL in `storage/repository.py`** — no raw SQL elsewhere
- **All services return `ResultEnvelope[T]`** from `mcp/envelope.py`
- **DI via `AppContainer`** in `services/container.py`
- **No circular imports** — imports flow downward only

## Test Suite Status (72 tests pass)
- 47 unit tests: ✅
- 20 acceptance tests: ✅
- 5 E2E tests (non-live): ✅
- All pass on `data` machine

## Quick Start for Dev
```bash
cd ~/my-projects/berlin-insolvency-radar
cp .env.example .env  # add DEEPSEEK_API_KEY
uv sync --extra dev
uv run biradar pipeline-check  # fixture-based dry run
uv run biradar serve  # MCP server
```
