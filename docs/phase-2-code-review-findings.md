# Phase 2 Code Review Findings

**Date:** 2026-06-16
**Reviewer:** Codex
**Verdict:** Phase 2 is locally verified end to end for the fixture-backed path, with live-complete status still gated by environment-dependent verification.

## Verification Performed

- Ran `uv run pytest`
- Result: `54 passed`
- Verified `biradar mcp-info` builds and exposes the Phase 2 MCP tool surface without outbound notification tooling
- Verified `radar_run_phase2_workflow` through the MCP execution path with `dry_run=true`
- Verified `uv run biradar phase2-check` passes against a temporary DuckDB using fixture-backed acquisition

## Issues Found And Fixed In This Round

### 1. Phase 2 modules imported a nonexistent logging package
- **Finding:** New Phase 2 code imported `biradar.observability.logging`, but the package did not exist. The Phase 2 test suite failed during collection.
- **Fix:** Added `src/biradar/observability/__init__.py` and `src/biradar/observability/logging.py`.

### 2. MCP Phase 2 workflow tool was still a placeholder
- **Finding:** `radar_run_phase2_workflow` returned a placeholder envelope instead of invoking the workflow.
- **Fix:** Wired the MCP tool to `run_phase2_pipeline(...)` and returned the real execution result envelope.

### 3. Phase 2 MCP surface violated the local-only boundary
- **Finding:** The repo still exposed `radar_notify_completion`, which contradicted the revised Phase 2 scope.
- **Fix:** Removed the outbound notification tool and its schema. Added a regression assertion in the Phase 0 acceptance gate that it is not present.

### 4. Checkpoint import was incompatible with the installed LangGraph package
- **Finding:** `langgraph.checkpoint.sqlite.SqliteSaver` was not available in the current environment, causing import-time failure.
- **Fix:** `CheckpointManager` now uses SQLite when the saver exists and falls back cleanly to `MemorySaver` otherwise.

### 5. Dry-run acquisition succeeded with zero records due to parser failure
- **Finding:** The official portal fixture starts with XML comments before the XML declaration. `_parse_response(...)` failed on that input, so the dry-run workflow exported an empty report while still reporting success.
- **Fix:** Sanitized leading comments before XML parsing and added a unit test for that case.

### 6. Parsed portal records did not carry legal form
- **Finding:** Parsed records lacked `legal_form`, so deterministic compliance could quarantine valid corporate filings.
- **Fix:** Added legal-form inference from the parsed company name in `official_portal.py`.

### 7. Workflow state dropped `issue_draft` before export
- **Finding:** `draft_assembly_node` wrote `issue_draft`, but `Phase2WorkflowState` did not declare it, so LangGraph dropped the field before the export node.
- **Fix:** Added `issue_draft` to `Phase2WorkflowState`.

### 8. Workflow terminal state was inconsistent
- **Finding:** The export node never set `current_step="completed"`, so the pipeline ended with `draft_assembly` as the reported final step.
- **Fix:** Normalized state transitions so draft assembly sets `current_step="export"` and the export node sets `current_step="completed"`.

### 9. Fixture-backed dry-run did not actually seed workflow source data
- **Finding:** The pipeline invoked the graph with empty `raw_records`, so the E2E only proved the placeholder path did not crash.
- **Fix:** `run_phase2_pipeline(...)` now loads and parses the official portal fixture for `dry_run=True` and seeds the graph with real parsed records.

### 10. Exports did not include actual computed score data
- **Finding:** The scoring node computed scores but did not attach them back onto candidates, so exported Markdown could not show real ranking data.
- **Fix:** Scoring results are now attached to each candidate.

### 11. Phase 2 MCP surface still lacked source-run inspection
- **Finding:** The revised plan expects source-run history inspection, but the MCP layer did not expose it.
- **Fix:** Added `SourceRunRepository.list_runs(...)`, `ListSourceRunsInput`, and the `radar_list_source_runs` MCP tool.

### 12. Phase 2 input dates lacked ordering validation
- **Finding:** The entrypoint accepted `end_date < start_date`.
- **Fix:** Added Pydantic model validation to reject inverted date windows.

### 13. Passed candidates never became `publish_ready`
- **Finding:** Risk review could pass a candidate, but the workflow never promoted it to `publish_ready`.
- **Fix:** Passing candidates now transition to `publish_ready`, and draft assembly only exports `publish_ready` candidates.

### 14. Successful live workflow results were not persisted into repo-owned product state
- **Finding:** The live Phase 2 path produced transient graph results and exported files, but did not write candidate/score/review/issue state back into DuckDB.
- **Fix:** Added a persistence pass in `run_phase2_pipeline(...)` for non-dry runs that writes:
  - candidates
  - candidate-to-raw links
  - extraction evidence
  - approved scores
  - risk review records
  - exported issue rows and issue-candidate links
  - audit events

### 15. Repeated Phase 2 runs were not idempotent at candidate level
- **Finding:** Candidate IDs were random when the workflow created canonical candidates, so repeated runs over the same record window produced duplicate candidate rows.
- **Fix:** Canonical candidate IDs now derive from the deterministic dedupe key when no candidate ID exists, making candidate persistence stable across repeated runs.

### 16. There was no persisted fixture-backed verification path for Phase 2
- **Finding:** The existing dry-run path only proved the transient graph path and did not verify source-run persistence, issue persistence, MCP source-run inspection, or repeat-run behavior.
- **Fix:** Added:
  - fixture-backed non-dry-run acquisition
  - `biradar phase2-check`
  - E2E coverage for persisted fixture-backed runs
  - MCP E2E coverage for `radar_list_source_runs` and `radar_run_phase2_workflow`

### 17. Risk review did not automatically reject unsupported enrichment claims
- **Finding:** Unsupported non-inference enrichment claims could survive to later stages if they lacked evidence URLs.
- **Fix:** Added deterministic pre-LLM risk-review checks that quarantine candidates with unsupported enrichment claims or missing extraction evidence, and record the reason in workflow state.

### 18. Export artifacts did not carry a structured run summary or explicit content separation
- **Finding:** Markdown and JSON exports lacked a run/audit summary and did not explicitly separate facts, inferences, and editorial context.
- **Fix:** Added:
  - `audit_summary` metadata to the issue draft and JSON package
  - Markdown run summary output
  - explicit `content_sections.facts`, `content_sections.inferences`, and `content_sections.editorial` per exported candidate
  - artifact assertions in E2E tests

### 19. Anti-bot handling was implemented but not verified directly
- **Finding:** The source adapter had a `blocked_by_anti_bot` branch, but there was no test proving retries stop after a 403/Cloudflare response.
- **Fix:** Added a unit test for `fetch_date_range(...)` that simulates a 403/Cloudflare response and verifies the adapter stops after the first blocked attempt.

## Current Status

The codebase now satisfies the following local verification bar:

- Phase 0 and Phase 1 suites still pass after the Phase 2 changes
- Phase 2 dry-run uses real parsed fixture input instead of an empty placeholder state
- Phase 2 fixture-backed persisted runs now verify source-run creation, raw-record persistence, candidate persistence, issue persistence, and repeat-run idempotency
- The MCP surface no longer exposes outbound notification behavior
- The Phase 2 workflow can be invoked from CLI, direct service call, and MCP
- The full repo test suite passes (`54 passed`, `87%` coverage)

## Remaining Gaps Before Calling Phase 2 Fully Complete

These are not open code defects from this round; they are remaining verification or environment gaps:

1. **Live official portal run not executed in this review**
   - The fixture-backed path is verified.
   - A real networked run against `neu.insolvenzbekanntmachungen.de` was not executed in this environment.

2. **Durable restart-safe checkpointing is not verified in this environment**
   - The code supports SQLite checkpointing when the LangGraph SQLite saver is installed.
   - The current environment only exposes the in-memory saver, so crash-resume durability was not verified here.

3. **Real model-backed agent path not verified in this review**
   - The workflow passes locally through safe mock fallback behavior when `DEEPSEEK_API_KEY` is absent.
   - The real LLM path and seeded eval quality still need live operator verification.

## Recommended Next Verification Step

Run a live dry-run with real credentials and the official portal enabled:

```bash
uv run biradar phase2-run --start-date 2026-06-10 --end-date 2026-06-16 --dry-run
```

Then verify:

- source-run history via `radar_list_source_runs`
- exported artifact contents
- audit trail contents
- non-mock agent behavior when the model key is present
