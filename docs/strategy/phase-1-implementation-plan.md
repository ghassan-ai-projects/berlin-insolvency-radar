# Phase 1 Implementation Plan: Legacy Import, Review, And Draft-Ready Core

**Date:** 2026-06-15
**Status:** Approved for execution after Phase 0
**Depends on:** Completed technical Phase 0 foundation
**Primary gate:** `docs/strategy/phase-acceptance-tests.md`, AT-1.0 through AT-1.12

---

## 1. Executive Summary

Phase 1 turns the Phase 0 skeleton into a usable local editorial workflow. It proves that OpenClaw or a developer can move from legacy or fixture source data to an audited, locally exported Markdown issue without touching the old production database, using external publishing, or relying on LLM policy decisions.

The Phase 1 workflow is:

```text
radar_health
  -> radar_import_legacy_scout { dry_run: true }
  -> radar_import_legacy_scout { dry_run: false }
  -> radar_list_candidates
  -> radar_get_candidate
  -> radar_review_candidate
  -> radar_create_issue_draft
  -> radar_export_issue
  -> radar_audit_trail
  -> radar_health
```

The product rule remains:

```text
agents suggest -> deterministic code verifies -> human approves -> audit log persists
```

Phase 1 is complete only when all Phase 0 gates still pass, all Phase 1 acceptance tests pass, and the workflow above is operable through the MCP tool/service path with fixture data.

---

## 2. Scope

### In Scope

- Fixture-backed legacy DuckDB import.
- Optional smoke compatibility with the real legacy DB opened read-only.
- Idempotent upserts into the repo-owned DuckDB.
- Compliance filtering and quarantine/rejection of personal or consumer records.
- Deduplication by canonical company/court/case/publication date key.
- Candidate list/detail views with evidence, source lineage, score status, and next actions.
- Deterministic review and score approval.
- Rejection, needs-more-info, duplicate, and archive review decisions.
- Local issue draft creation from approved candidates only.
- Local Markdown export only.
- Audit trail for every successful and failed state-changing attempt.
- Full fixture-based integration and acceptance tests.
- Documentation for the Phase 1 workflow.

### Out Of Scope

- Fresh official-portal scraper.
- Live `neu.insolvenzbekanntmachungen.de` acquisition.
- beehiiv API, email sending, alerts, Telegram, Slack, or external publishing.
- Third-party enrichment APIs.
- LLM extraction, enrichment, scoring, or publishing decisions.
- Hosted deployment, multi-user writes, Postgres migration, or background scheduler.
- Product launch tasks such as legal consult, beehiiv setup, or subscriber landing page.

---

## 3. Current Starting Point

Phase 0 provides:

- Python 3.12 project with `uv`, Ruff, Pyright, pytest, and pytest-cov.
- DuckDB schema creation for core tables.
- MCP v0 server exposing exactly 8 tools.
- Shared `ResultEnvelope`.
- Health and audit tool paths.
- Deterministic compliance, dedupe, scoring, and status modules.
- Phase 0 LangGraph health workflow.
- Unit tests and Phase 0 acceptance tests.

Known Phase 1 gaps from `docs/phase-0-plan-traceability.md`:

- SQL is not fully centralized in repositories.
- Legacy import is not a real idempotent upsert implementation.
- Integration tests and Phase 1 fixtures do not exist yet.
- Most MCP tools do not yet have dedicated Pydantic input models.
- Review, draft, export, and audit behavior are scaffolding until fixture tests prove them.

---

## 4. Acceptance Gate Mapping

| Gate | Implementation focus | Required proof |
|---|---|---|
| AT-1.0 Legacy production DB is never mutated | read-only legacy connection, path guard, hash/mtime checks | fixture and optional real-DB smoke tests assert unchanged input |
| AT-1.1 Dry run writes nothing | dry-run import plan | zero persisted raw/candidate/evidence/source-run rows |
| AT-1.2 Real import is idempotent | upsert raw records, candidates, candidate sources, source runs | second import creates no duplicate candidates; run/audit history exists |
| AT-1.3 Corporate filter | compliance policy in import and status gates | allowed forms become candidates; personal/consumer rows cannot publish |
| AT-1.4 Candidate list queue | list summaries and ordering | default output is actionable queue with evidence/score/status/next action |
| AT-1.5 Candidate detail | evidence and lineage joins | detail includes candidate, raw sources, evidence, reviews, scores, audit/source lineage |
| AT-1.6 Approve and score | review service + scoring + transaction | status `publish_ready`, approved score row, review row, audit event |
| AT-1.7 Reject/needs-more-info | review decisions and note requirements | note required where policy requires; no accidental approved score |
| AT-1.8 Invalid transitions blocked | status state machine + failed-attempt audit | no status change, stable error, audit of failed attempt |
| AT-1.9 Draft approved candidates only | issue draft gate | rejects unapproved/quarantined/no-evidence candidates; suppresses restricted free-tier fields |
| AT-1.10 Export Markdown only | local file export | writes configured path, persists timestamp/path, no external calls |
| AT-1.11 Audit trail explains history | audit linking | import, candidate creation/dedupe, review, score, issue/export visible |
| AT-1.12 Health reports work remaining | health summaries | counts, last source run, stale state, next action |

---

## 5. Data And Fixture Design

### Fixture Layout

Create:

```text
tests/fixtures/phase1/
  legacy_fixture.duckdb
  fixture_rows.json
  expected_import_summary.json
  expected_issue_free.md
```

`legacy_fixture.duckdb` should be generated deterministically from `fixture_rows.json` by a test helper, not checked in if binary fixtures become awkward. If generated, keep the generator under:

```text
tests/fixtures/phase1/build_legacy_fixture.py
```

### Required Fixture Records

Include at minimum:

- Berlin GmbH filing, valid.
- Berlin UG filing, valid.
- GmbH & Co. KG filing, valid.
- AG or SE filing, valid.
- Duplicate source rows for the same company/court/case/date.
- Individual debtor or consumer-style text, must quarantine or reject.
- Sole proprietor/e.K. record, must quarantine or reject.
- Ambiguous legal form, must become `needs_review` or `quarantined` according to policy.
- Malformed source row, must not crash import and must produce warning/error data.
- Candidate with no evidence, must be blocked from issue draft.

### Fixture Table Contract

The legacy fixture DB should have a minimal `filings` table with fields the importer explicitly supports:

```text
filing_id
company_name
legal_form
court
case_number
register_number
publication_date
publication_type
source_url
raw_text
scraped_at
```

If the real legacy DB uses different names, implement a small adapter/mapping layer and document it in `LegacyImportService`. Tests should pin that mapping.

---

## 6. Implementation Tasks

### Task 1: Repository And Transaction Boundaries

Goal: make storage behavior testable, centralized, and safe before import/review logic grows.

Implement or expand repositories:

- `RawRecordRepository`
- `CandidateRepository`
- `EvidenceRepository`
- `SourceRunRepository`
- `ReviewRepository`
- `ScoreRepository`
- `IssueRepository`
- `AuditRepository`

Required methods:

- create source run, complete source run, fail source run.
- upsert raw record by content hash or source/external id.
- upsert candidate by dedupe key or canonical identity.
- link candidate to raw record.
- insert evidence item.
- list candidate summaries with evidence count and score status.
- get candidate detail with evidence, scores, reviews, source records, and audit lineage.
- update candidate status.
- insert review.
- insert approved score.
- create issue draft and issue candidates.
- export/update issue status.
- write and query audit events.

Rules:

- Services orchestrate; repositories persist.
- No SQL in MCP handlers or domain modules.
- Move service SQL into repositories where it supports Phase 1 behavior.
- Failed state-changing attempts must be audited when the request reaches application logic.

Acceptance:

- `rg "conn\\.execute|duckdb\\.connect" src/biradar/services src/biradar/graph src/biradar/mcp` shows only approved exceptions, such as the legacy read-only adapter and explicitly documented workflow count checks.
- Pyright and Ruff pass.

### Task 2: Pydantic MCP Input Models

Goal: make every v0 tool input explicit and stable for agents.

Add models, preferably in `src/biradar/mcp/schemas.py`:

- `HealthInput`
- `ImportLegacyScoutInput`
- `ListCandidatesInput`
- `GetCandidateInput`
- `ReviewCandidateInput`
- `ScoreInput` reuse or wrapper
- `CreateIssueDraftInput`
- `ExportIssueInput`
- `AuditTrailInput`

Rules:

- Use strict enums for review decisions, statuses, tier, and format.
- `dry_run` defaults to `true` for import.
- State-changing tools require `actor` or `reviewer`.
- Validation failures return stable `VALIDATION_ERROR`.
- All tools return `ResultEnvelope`.

Acceptance:

- MCP contract tests cover input validation and envelope shape for all 8 tools.

### Task 3: Real Legacy Import

Goal: turn legacy import from simulation into a deterministic, idempotent source ingestion path.

Behavior:

- Reject legacy path if it resolves to the active radar DB.
- Open legacy DB with `duckdb.connect(path, read_only=True)`.
- Record pre-import size, mtime, and SHA-256 hash.
- Read supported rows from `filings`.
- Normalize rows into an internal source-record shape.
- Compute raw content hash from stable source fields.
- Apply compliance policy.
- Compute dedupe key from company name, court, case number, and publication date.
- In `dry_run=true`, return counts and warnings without persisting source runs, raw records, candidates, evidence, or audit events unless the team intentionally decides dry-run audits are useful. The acceptance spec says no source runs are persisted.
- In `dry_run=false`, persist source run, raw records, candidates, candidate links, evidence, and audit events in a transaction.
- Re-run import safely without duplicate candidates.
- Verify post-import legacy size, mtime, and hash match pre-import.

Import status policy:

- Clear corporate records with required evidence: `review_ready`.
- Ambiguous legal form: `needs_review` or `quarantined` with risk flag.
- Consumer/personal/sole proprietor: `quarantined` or `rejected`.
- Malformed row: counted as rejected or warning; source-run error data records reason.

Evidence policy:

- Every imported candidate must receive evidence for at least company name, court/case/publication date where present, and source URL/raw snippet.
- Evidence content hashes should be deterministic.
- LLM output is never evidence.

Acceptance:

- AT-1.0, AT-1.1, AT-1.2, and AT-1.3 pass.

### Task 4: Candidate List And Detail

Goal: make the candidate queue usable without manual DuckDB inspection.

`radar_list_candidates` must return summaries with:

- candidate id.
- company name.
- legal form.
- court.
- case number.
- publication date.
- status.
- evidence count.
- source count.
- score status and latest score if any.
- risk flags.
- next action.

Default status filter:

```text
needs_review, review_ready
```

Ordering:

- candidates needing review first.
- newest publication date or created time first within status groups.

`radar_get_candidate` must return:

- normalized candidate fields.
- linked raw source records.
- evidence items.
- previous reviews.
- scores.
- risk flags.
- source-run lineage.
- candidate audit history.

Sensitive data:

- Consumer/personal records should already be quarantined or rejected.
- Detail output should suppress obviously personal data by default unless needed for compliance investigation.

Acceptance:

- AT-1.4 and AT-1.5 pass.

### Task 5: Review And Scoring

Goal: make editorial approval deterministic, auditable, and hard to bypass.

Supported decisions:

- `approve`
- `reject`
- `needs_more_info`
- `mark_duplicate`
- `archive`

Rules:

- Use `domain/statuses.py` for transitions.
- Approval requires valid score dimensions and at least one evidence item.
- Approval from quarantined/rejected directly to publish-ready is blocked.
- Reject and needs-more-info require a reviewer note.
- Mark duplicate should preserve the duplicate reason and, when available, the canonical candidate id.
- Every success writes review row and audit event.
- Every failed state-changing attempt that reaches service logic writes audit event with failure result.
- Score is computed only by deterministic code using `config/scoring.yaml`.
- Score row status is `approved` only after approval.

Acceptance:

- AT-1.6, AT-1.7, and AT-1.8 pass.

### Task 6: Issue Draft And Local Export

Goal: create useful local newsletter drafts without any external publishing risk.

`radar_create_issue_draft` rules:

- Accept explicit `candidate_ids`.
- Validate all included candidates are `publish_ready`.
- Require approved score.
- Require at least one evidence item.
- Block rejected, quarantined, duplicate, archived, and no-evidence candidates.
- Return warnings for skipped candidates only if the request policy allows partial drafts. Prefer fail-fast for explicit candidate lists unless tests specify otherwise.
- Free tier suppresses administrator contacts and restricted fields.
- Include disclaimer text.
- Persist issue and issue candidate links.
- Write audit event.

`radar_export_issue` rules:

- Only `markdown` supported in Phase 1.
- Write under `data/exports/` by default, or a temp export path in tests.
- Persist `exported_at` and `export_path`.
- Write audit event.
- Never call beehiiv, email, alert, webhook, or network publishing code.

Markdown should follow `docs/strategy/newsletter-template.md` closely enough that it is usable as an editorial draft.

Acceptance:

- AT-1.9 and AT-1.10 pass.

### Task 7: Health And Audit Trail

Goal: make the app operable by asking “what happened?” and “what now?”

Health must report:

- database connection and path.
- schema version.
- counts by candidate status.
- last successful source run.
- stale source state.
- next action based on queue state.

Audit trail must show:

- import/source-run event.
- candidate creation or dedupe event.
- review decision.
- score approval.
- issue inclusion/export event.
- failed write attempts where relevant.

Acceptance:

- AT-1.11 and AT-1.12 pass.

### Task 8: LangGraph Workflow Coverage

Goal: use LangGraph for real Phase 1 orchestration without making it the policy owner.

Add or expand workflows:

- import workflow: dry-run and real import paths.
- review workflow: approve, reject, needs-more-info, invalid transition.
- issue workflow: draft and export path.

Rules:

- Graph state carries IDs, counts, actor, status, and error metadata.
- Durable facts stay in DuckDB.
- Deterministic modules decide compliance, dedupe, scoring, and gates.

Acceptance:

- Workflow tests assert final state and database side effects.
- Phase 0 health workflow remains green.

---

## 7. Test Plan

### Unit Tests

Keep and expand:

- compliance allowlist and consumer indicators.
- dedupe normalization and key stability.
- scoring thresholds.
- status transitions and note/score requirements.
- issue selection/free-tier suppression helpers if extracted.
- repository helper methods that are pure enough to unit test.

### Integration Tests

Create:

```text
tests/integration/test_phase1_legacy_import.py
tests/integration/test_phase1_candidate_review.py
tests/integration/test_phase1_issue_export.py
tests/integration/test_phase1_audit_health.py
```

Must use temp DuckDB files and generated fixtures, never `data/radar.duckdb`.

Cover:

- fixture legacy DB unchanged after dry-run and real import.
- dry-run writes nothing.
- real import persists raw records, candidates, links, evidence, source run, audit.
- repeated import is idempotent.
- duplicate source rows collapse into one candidate.
- review approve/reject/needs-more-info/duplicate/archive.
- invalid transition returns stable error and audit.
- issue draft blocks unapproved/quarantined/no-evidence candidates.
- export writes local Markdown and persists export metadata.
- health updates after import/review/export.

### MCP Contract Tests

Create:

```text
tests/contract/test_mcp_v0_tools.py
```

Cover all 8 tools:

- valid input success envelope.
- invalid input failure envelope.
- state-changing audit behavior.
- `dry_run` behavior for import.
- useful `next_action` where expected.

### Acceptance Tests

Create:

```text
tests/acceptance/test_phase1_legacy_import_review.py
```

This should map directly to AT-1.0 through AT-1.12. Keep tests readable and product-facing; push lower-level checks into integration tests.

### Manual Acceptance

Run the 10-step script from `phase-acceptance-tests.md` through MCP or `call_radar_tool` using the fixture DB. Save the command/result summary in `docs/phase-1-review.md` when complete.

---

## 8. Makefile And Verification Commands

Update `Makefile` so Phase 1 has an explicit gate:

```make
phase1-check: phase0-check test-integration test-contract
```

If a separate contract target is not desired, include contract tests in `test-acceptance` or `test-integration`, but document the choice.

Expected commands:

```bash
uv run make phase0-check
uv run make test-integration
uv run make phase1-check
uv run biradar mcp-info
```

Phase 1 is not done unless `uv run make phase1-check` passes.

---

## 9. Documentation Updates

Update:

- `README.md`: Phase 1 workflow commands and fixture-based demo.
- `docs/phase-1-review.md`: completion review, verification output, residual risks.
- `docs/strategy/phase-acceptance-tests.md`: only if acceptance wording is clarified, not weakened.
- `docs/strategy/mcp-interface.md`: if input schemas or response fields change.
- `docs/phase-0-plan-traceability.md`: only if Phase 1 closes a previously noted gap.

Do not mark product launch tasks complete unless they are actually done outside the repo.

---

## 10. Definition Of Done

Phase 1 is done only when:

- all Phase 0 acceptance tests still pass.
- AT-1.0 through AT-1.12 pass.
- `uv run make phase1-check` passes.
- fixture tests use temp DuckDB files and do not mutate real project data.
- optional real legacy DB smoke test opens read-only and verifies hash/mtime unchanged.
- dry-run import writes nothing.
- real import is idempotent.
- duplicate legacy rows do not become duplicate newsletter candidates.
- personal/consumer records cannot reach `publish_ready`.
- candidate list/detail is usable without manual DuckDB inspection.
- review can approve, reject, request more info, archive, and mark duplicates.
- deterministic score calculation is stored and audited.
- failed state-changing attempts are audited.
- issue draft and export work locally.
- no external publish/send/alert code path is active.
- README explains how to run the Phase 1 workflow.
- `docs/phase-1-review.md` records completion evidence and residual risks.

Phase 1 is not done if:

- agents must know table names or manually query DuckDB.
- the legacy DB can be opened in write mode.
- tests write to `data/radar.duckdb`.
- failed writes disappear without audit.
- LLM output can create evidence.
- unapproved or no-evidence candidates can be exported.
- external publishing code is active or reachable from MCP.

---

## 11. Suggested Execution Order

1. Add fixtures and fixture DB generator first.
2. Add repository methods and move service SQL behind repositories.
3. Add Pydantic MCP input models and contract tests.
4. Implement dry-run import and prove it writes nothing.
5. Implement real idempotent import and source-run/audit history.
6. Implement candidate summaries/details with evidence and lineage.
7. Harden review decisions, scoring, status transitions, and failed-attempt audit.
8. Harden issue draft/export gates and Markdown output.
9. Add health/audit trail completion behavior.
10. Add Phase 1 acceptance tests and manual acceptance review.

This order keeps safety and test fixtures ahead of feature work, which is exactly where this project wants its center of gravity.
