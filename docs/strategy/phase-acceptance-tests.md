# Phase Acceptance Tests

**Date:** 2026-06-15
**Status:** Required acceptance gates for Phase 0 and Phase 1

---

## Purpose

This document defines what "done" means for the first implementation phases.

The goal is to prevent a familiar failure mode: a project that technically has modules, tools, and tests, but cannot complete the real workflow end to end. A phase is not done because code exists. A phase is done when the system can pass the acceptance tests below using a clean local setup and fixture data.

These acceptance tests are product gates. They sit above unit/integration tests and prove that the MCP-first, DuckDB-backed, LangGraph-orchestrated application is usable by OpenClaw and safe for human review.

---

## Acceptance Test Conventions

Each acceptance test should be automated where possible.

Recommended location:

```text
tests/acceptance/
  test_phase0_foundation.py
  test_phase1_legacy_import_review.py
```

Acceptance tests should:

- use a temporary DuckDB database, never `data/radar.duckdb`
- use fixtures, never the live official portal
- treat `/Users/ghassan/my-projects/insolvency-scout/data/insolvency_scout.duckdb` as production data
- prefer representative fixture copies over the live legacy DB
- open the live legacy DuckDB read-only if an optional smoke test needs it
- assert that any legacy DB used as input is unchanged after import
- call MCP tool handlers or the same application services used by MCP tools
- assert user/agent-facing outputs, not only internal rows
- verify audit events for every state-changing operation

Acceptance tests may run slower than unit tests, but they should still be reliable enough for CI.

---

## Phase 0: Foundation And Skeleton

### Phase Goal

Phase 0 proves that the project has a working application skeleton:

- Python package boots
- DuckDB schema can be created
- MCP server/tool layer can respond
- configuration is typed and loadable
- audit writes work
- LangGraph can run a minimal workflow shell
- no production data or old pipeline is mutated

Phase 0 does **not** need legacy import, candidate review, scoring approval, or issue generation.

### Phase 0 Acceptance Tests

#### AT-0.1 Fresh Database Boot

**Given** a clean temporary workspace with no database file
**When** the application initializes storage
**Then** it creates a DuckDB database with the expected schema version
**And** required tables exist:

- `schema_migrations`
- `source_providers`
- `source_runs`
- `raw_records`
- `candidates`
- `candidate_sources`
- `evidence_items`
- `scores`
- `reviews`
- `issues`
- `issue_candidates`
- `audit_events`

**Done means:** a new developer or agent can start the app without manually creating tables.

#### AT-0.2 Health Tool Works On Fresh DB

**Given** a fresh initialized DuckDB database
**When** `radar_health` is called
**Then** it returns `ok: true`
**And** reports:

- database connected
- database path
- schema version
- candidate counts equal to zero
- no successful source run yet
- a clear `next_action`

**Done means:** OpenClaw can ask "what now?" and receive a useful answer.

#### AT-0.3 Result Envelope Is Stable

**Given** any v0 MCP tool handler
**When** it succeeds or fails validation
**Then** the response uses the shared envelope:

- `ok`
- `data`
- `warnings`
- `errors`
- `audit_id`

**And** errors include:

- stable `code`
- concise `message`
- `retryable`
- optional `next_action`

**Done means:** agents can program against the MCP surface predictably.

#### AT-0.4 Audit Event Can Be Written And Read

**Given** an initialized database
**When** a test audit event is written through the audit service
**Then** `radar_audit_trail` can retrieve it
**And** it includes:

- actor
- action
- entity type
- entity id
- request summary
- result summary
- timestamp

**Done means:** the application has the spine needed for accountable automation.

#### AT-0.5 Config Loads And Validates

**Given** default config files for scoring and sources
**When** the app starts
**Then** config loads into typed models
**And** invalid config fails with an actionable error
**And** no secret value is required for Phase 0.

**Done means:** settings are explicit and not hidden in code.

#### AT-0.6 Minimal LangGraph Workflow Runs

**Given** a no-op or health-check LangGraph workflow
**When** it is invoked through the application layer
**Then** it returns a typed final state
**And** records a workflow/audit marker
**And** does not write candidates or source records.

**Done means:** LangGraph is integrated from v0 without pretending the agentic workflow is finished.

#### AT-0.7 Safety Defaults

**Given** a Phase 0 build
**When** tests inspect available tools and config
**Then** there is no enabled external publishing, email sending, alert sending, or live scraper schedule
**And** any legacy DB path is treated as read-only.

**Done means:** the skeleton cannot accidentally become a production sender or parallel pipeline.

### Phase 0 Done Means

Phase 0 is complete only when:

- all Phase 0 acceptance tests pass
- `make check` passes
- a fresh DuckDB can be initialized from zero
- `radar_health` and `radar_audit_trail` work
- the MCP server can start locally
- the minimal LangGraph workflow is callable
- no live acquisition, external publish, email, or alert path is enabled
- documentation reflects how to run the skeleton

Phase 0 is **not** done if:

- tables must be created manually
- MCP tools return inconsistent response shapes
- errors are raw stack traces
- tests touch the real development DB
- the legacy DB can be mutated
- LangGraph exists only as an unused dependency

---

## Phase 1: Legacy Import, Candidate Review, And Draft-Ready Core

### Phase Goal

Phase 1 proves that the system can complete the first real product workflow using legacy or fixture data:

```text
health
  -> legacy import
  -> candidate list/detail
  -> review and score
  -> audit trail
  -> create local issue draft
  -> export Markdown
```

Phase 1 does not require the fresh official scraper or paid APIs.

### Required Fixtures

Phase 1 acceptance tests need fixture records representing:

- a Berlin GmbH filing
- a Berlin UG filing
- a GmbH & Co. KG filing
- duplicate records for the same company/date/case
- an individual debtor or consumer-style record that must be quarantined
- an ambiguous legal form that must require review
- a malformed source row
- a candidate with no evidence

Fixtures can be built from sanitized legacy records or handcrafted samples.

### Phase 1 Acceptance Tests

#### AT-1.0 Legacy Production DB Is Never Mutated

**Given** a legacy DuckDB input path
**And** its file size, modified time, and content hash are recorded before import
**When** `radar_import_legacy_scout` runs in dry-run or real-import mode
**Then** the legacy DuckDB file is opened read-only
**And** the repo-owned DuckDB receives all writes
**And** the legacy file size, modified time, and content hash are unchanged after import
**And** the import fails if the legacy input path points to `data/radar.duckdb`.

**Done means:** the old database is treated as production input, not as this project's working database.

#### AT-1.1 Legacy Import Dry Run Writes Nothing

**Given** a fixture legacy DuckDB or fixture import provider with mixed records
**When** `radar_import_legacy_scout` is called with `dry_run: true`
**Then** it returns `ok: true`
**And** reports:

- raw records seen
- distinct candidate count
- duplicate count
- rejected/quarantined count
- would-import count
- warnings

**And** no `raw_records`, `candidates`, `evidence_items`, or `source_runs` are persisted.

**Done means:** agents can safely preview imports.

#### AT-1.2 Legacy Import Real Run Is Idempotent

**Given** the same fixture legacy input
**When** `radar_import_legacy_scout` is called with `dry_run: false` twice
**Then** the second run does not create duplicate candidates
**And** duplicate source rows link to the same canonical candidate
**And** both import attempts are visible through source-run/audit history.

**Done means:** repeated agent runs are safe.

#### AT-1.3 Corporate Filter Allows Only Supported Company Forms

**Given** imported fixture records
**When** the import workflow applies the corporate filter
**Then** GmbH, UG, AG, KG, OHG, GmbH & Co. KG, eG, and SE records can become candidates
**And** consumer, personal, sole-proprietor, or unclear records become `quarantined`, `rejected`, or `needs_review` according to policy
**And** quarantined records cannot reach `publish_ready`.

**Done means:** compliance is enforced by code, not prompt text.

#### AT-1.4 Candidate List Defaults To Agent Work Queue

**Given** imported candidates in several statuses
**When** `radar_list_candidates` is called without filters
**Then** it returns candidates needing work first
**And** each summary includes:

- candidate id
- company name
- legal form
- court
- publication date
- status
- evidence count
- score status
- risk flags
- next action

**Done means:** OpenClaw gets an actionable queue, not a raw database dump.

#### AT-1.5 Candidate Detail Shows Evidence And Lineage

**Given** an imported candidate
**When** `radar_get_candidate` is called
**Then** it returns:

- normalized candidate fields
- linked raw source records
- evidence items
- previous reviews
- scores
- risk flags
- audit/source lineage

**And** sensitive personal data is suppressed by default.

**Done means:** a reviewer can understand why the candidate exists.

#### AT-1.6 Review Approves Candidate And Score

**Given** a `review_ready` corporate candidate with evidence
**When** `radar_review_candidate` is called with `decision: approve` and valid score dimensions
**Then** the candidate moves to `publish_ready`
**And** a deterministic score is computed
**And** a score row is stored as approved
**And** a review row is stored
**And** an audit event is written
**And** the response includes the computed score and next action.

**Done means:** the core editorial approval loop works.

#### AT-1.7 Review Rejects Or Requests More Info

**Given** a candidate needing review
**When** `radar_review_candidate` is called with `reject` or `needs_more_info`
**Then** the status changes accordingly
**And** reviewer note is required
**And** no approved score is created unless explicitly valid and allowed
**And** an audit event is written.

**Done means:** review is not only a happy-path approval button.

#### AT-1.8 Invalid Status Transitions Are Blocked

**Given** a quarantined or rejected candidate
**When** an agent attempts to mark it `publish_ready` directly
**Then** the tool returns `ok: false`
**And** the error code is stable
**And** no candidate status changes
**And** the failed attempt is audited.

**Done means:** MCP cannot bypass workflow gates.

#### AT-1.9 Issue Draft Uses Only Approved Candidates

**Given** a mix of approved, unapproved, rejected, and quarantined candidates
**When** `radar_create_issue_draft` is called
**Then** only `publish_ready` candidates with approved scores and evidence can be included
**And** candidates without evidence are rejected from the draft with warnings
**And** free-tier output suppresses restricted fields.

**Done means:** public draft creation respects review and compliance gates.

#### AT-1.10 Export Writes Local Markdown Only

**Given** a valid issue draft
**When** `radar_export_issue` is called with `format: markdown`
**Then** a Markdown file is written under `data/exports/` or a configured temp export path
**And** no beehiiv API, email, alert, or external publish operation is called
**And** export path and timestamp are persisted
**And** an audit event is written.

**Done means:** the product can create useful output without external publishing risk.

#### AT-1.11 Audit Trail Explains Candidate History

**Given** an imported, reviewed, and exported candidate
**When** `radar_audit_trail` is called for that candidate
**Then** it shows:

- import/source-run event
- candidate creation/dedupe event
- review decision
- score approval
- issue inclusion/export event

**Done means:** the system can explain how a candidate moved from source data to newsletter draft.

#### AT-1.12 Health Reports Real Work Remaining

**Given** a Phase 1 database with imported candidates
**When** `radar_health` is called
**Then** it reports counts by status
**And** stale-source state
**And** last import/source run
**And** recommended next action, such as reviewing candidates or exporting an issue.

**Done means:** OpenClaw can operate the queue without guessing.

### Phase 1 Done Means

Phase 1 is complete only when:

- all Phase 0 acceptance tests still pass
- all Phase 1 acceptance tests pass
- `make check` passes
- `make test-integration` passes
- the real legacy production DB is never mutated
- tests use fixture copies or temp clones by default
- legacy import supports dry-run and real import
- real import is idempotent
- candidates are deduped
- personal/consumer records cannot become publish-ready
- candidate list/detail is useful to an agent
- review can approve, reject, request more info, archive, and mark duplicates
- approved score calculation is deterministic
- every state-changing MCP tool writes audit
- issue draft and export work locally
- no external publish/send/alert code path is active
- documentation explains how to run the Phase 1 workflow

Phase 1 is **not** done if:

- a human must inspect DuckDB manually to operate the workflow
- agents need to know internal table names
- duplicate legacy rows appear as separate newsletter candidates
- LLM output can create evidence
- unapproved candidates can be exported
- tests use the real legacy DB in write mode
- failed writes disappear without audit

---

## Done Means Across Both Phases

For Phase 0 and Phase 1, "done" means the product is safe, inspectable, and operable. Specifically:

- a clean checkout can initialize and run the app locally
- OpenClaw can interact through MCP only
- DuckDB is the single repo-owned state store
- legacy data is read-only input
- LangGraph coordinates real workflow steps
- deterministic code owns compliance, dedupe, scoring, status transitions, audit, and export gates
- every public-output path requires evidence and review
- tests prove the intended behavior end to end
- no old and new production pipelines are running together

---

## Manual Acceptance Script

Before declaring Phase 1 complete, run the workflow manually once through MCP or the CLI-equivalent service calls:

```text
1. radar_health
2. radar_import_legacy_scout { dry_run: true }
3. radar_import_legacy_scout { dry_run: false }
4. radar_list_candidates
5. radar_get_candidate { candidate_id }
6. radar_review_candidate { decision: approve, score: ... }
7. radar_create_issue_draft
8. radar_export_issue
9. radar_audit_trail { candidate_id }
10. radar_health
```

The run is accepted only if:

- the agent-facing responses are understandable
- each write has an audit id
- the exported Markdown is usable as an editorial draft
- no external system receives data
- the health response gives the next sensible action
