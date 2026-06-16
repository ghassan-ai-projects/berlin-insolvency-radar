# Phase 0 Implementation Plan: Foundation & MCP v0

**Date:** 2026-06-15
**Goal:** Build the smallest viable, safe, and auditable application skeleton for the Berlin Insolvency Radar.
**Status:** Complete

---

## 1. Step-by-Step Implementation

### Step 1: Project Scaffolding & Configuration
- Initialize Python 3.12+ project with `pyproject.toml` (`duckdb`, `pydantic`, `langgraph`, `mcp`, `ruff`, `pytest`, `pytest-cov`).
- Create directory structure: `src/biradar/`, `data/`, `tests/`, `data/exports/`, `config/`.
- Add typed configuration loaders for `config/scoring.yaml` (v1 weights) and `config/sources.yaml` (legacy DB path explicitly marked read-only).
- Create `Makefile` with `check`, `test`, `lint`, `typecheck` targets.

### Step 2: Database Schema & Repository Layer
- Implement `storage/migrations/` to create core DuckDB tables: `schema_migrations`, `source_providers`, `source_runs`, `raw_records`, `candidates`, `candidate_sources`, `evidence_items`, `scores`, `reviews`, `issues`, `issue_candidates`, `audit_events`.
- Build `storage/repository.py` to centralize all DuckDB access (no ad-hoc SQL in services).
- Implement append-only audit event writes through the repository layer.

### Step 3: Deterministic Domain Modules
- `domain/compliance.py`: Corporate legal-form allowlist (GmbH, UG, AG, KG, OHG, SE, eG) and quarantine logic for consumer/personal filings.
- `domain/dedupe.py`: Matching keys (company name + court + case number + publication date).
- `domain/scoring.py`: Deterministic v1 formula with config-driven weights.
- `domain/statuses.py`: State machine validation for candidate transitions.

### Step 4: Application Services
- `HealthService`: Returns DB status, schema version, candidate counts by status, and a clear `next_action`.
- `LegacyImportService`: Read-only adapter for the legacy `insolvency_scout.duckdb`. Supports `dry_run`, idempotent upserts, and strict validation that the legacy DB file hash remains unchanged.
- `CandidateService`: `list` (defaults to `needs_review` work queue) and `get` (returns candidate + evidence + lineage).
- `ReviewService`: Single endpoint to approve/reject/needs_info, update status, store optional validated score, and write audit event.
- `IssueService`: Selects `publish_ready` candidates, generates Markdown, and exports to `data/exports/` (no external API calls).

### Step 5: LangGraph Workflow Shell
- Implement minimal `graph/phase0_workflow.py` and `graph/review_workflow.py`.
- Ensure durable state relies on DuckDB IDs, not large payloads in graph state.

### Step 6: MCP Server v0 Contract
- Implement `mcp/server.py` exposing exactly 8 tools with typed Pydantic inputs and the unified result envelope (`ok`, `data`, `warnings`, `errors`, `audit_id`, `next_action`):
  1. `radar_health`
  2. `radar_import_legacy_scout`
  3. `radar_list_candidates`
  4. `radar_get_candidate`
  5. `radar_review_candidate`
  6. `radar_create_issue_draft`
  7. `radar_export_issue`
  8. `radar_audit_trail`

### Step 7: Testing & Acceptance Gates
- **Unit Tests:** Scoring formula, legal-form allowlist, deduplication, status transitions.
- **Integration Tests:** Legacy import idempotency, read-only enforcement (asserting unchanged legacy file hash), audit writes.
- **Acceptance Tests:** AT-0.1 to AT-0.7 as defined in `docs/strategy/phase-acceptance-tests.md`.

---

## 2. Safety & Compliance Non-Negotiables

- **Legacy DB Protection:** Opened strictly read-only. Tests will explicitly assert its file size and content hash are unchanged.
- **No External Publishing:** v0 only exports local Markdown. No beehiiv API, email, or alert integrations.
- **Deterministic Controls:** Compliance filtering, deduplication, and scoring are enforced by Python code, not LLM prompts.
- **Audit Everything:** Every state-changing MCP tool call must generate an `audit_events` row.

---

## 3. Verification

- Run `make check` (lint, typecheck, format).
- Run `pytest tests/acceptance/test_phase0_foundation.py` to prove all Phase 0 acceptance gates pass.
- Manually invoke the 8 MCP tools via a local MCP inspector to verify the OpenClaw happy path.
