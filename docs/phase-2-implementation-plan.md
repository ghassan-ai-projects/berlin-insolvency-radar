# Phase 2 Implementation Plan: Fully Agentic Local Pipeline

**Date:** 2026-06-16  
**Status:** Revised after review  
**Scope:** End-to-end autonomous local workflow from official portal acquisition to export-ready issue artifacts, without human review, paid sources, or external publishing.

---

## 1. Executive Summary

Phase 2 transitions the Berlin Insolvency Radar from a human-in-the-loop MCP v0/Phase 1 system to a **fully agentic, local-only pipeline**. The system will autonomously ingest data from `neu.insolvenzbekanntmachungen.de`, normalize, extract, enrich, score, risk-review, and assemble export-ready Markdown/JSON issue packages. 

**Core Principle:** Agents execute the workflow; deterministic code verifies guardrails; logs remember everything. No human review is required for the pipeline to complete, and no paid APIs or datasets are used.

---

## 2. Phase 2 Definition & Core Objectives

Phase 2 is defined by the following non-negotiable objectives:
1. **Repo-Owned Acquisition:** A native source adapter for `neu.insolvenzbekanntmachungen.de` replaces reliance on the legacy `insolvency-scout` pipeline.
2. **Fully Agentic Execution:** A complete LangGraph workflow handles ingest → normalize → compliance → dedupe → extraction → enrichment → scoring → risk review → draft assembly → export.
3. **Zero Human Intervention:** The workflow must complete end-to-end without manual approval or review steps.
4. **Free/Public Sources Only:** Enrichment and data gathering use strictly official, free, or public sources. No paid APIs, paid archives, or commercial datasets.
5. **Local Export Only:** The output is a local, publish-ready artifact package (Markdown + JSON + audit metadata). External publishing remains disabled.

---

## 3. Definition of Done (Strict)

Phase 2 is **only** considered complete when all the following conditions are met simultaneously:

- [ ] A scheduled local run successfully goes from fresh official acquisition to an export-ready local issue package through the full agent workflow.
- [ ] Zero human review or manual intervention is required for the run to complete.
- [ ] Zero paid features, paid APIs, or paid data sources are required or invoked.
- [ ] The new scraper matches or exceeds legacy candidate coverage for at least one sampled historical date window, with any gaps explained.
- [ ] Deterministic, code-owned guardrails (compliance filtering, deduplication, scoring formulas, quarantine thresholds, and export gates) remain intact and enforce policy.
- [ ] The entire workflow is covered by unit, integration, workflow, and E2E tests, with at least one successful E2E fixture run validating the complete path.
- [ ] Old `insolvency-scout` production jobs remain explicitly disabled.

---

## 4. Acceptance Criteria (By Capability)

### 4.1 Official Acquisition & Observability
- Adapter runs independently of legacy pipelines.
- Implements request retries, timeouts, and structured parse error handling.
- Empty-result days are logged as successful zero-result runs, not failures.
- Repeated runs over the same date window are strictly idempotent.
- Every acquisition attempt writes a `source_run` record with status, params, timestamps, counts, duplicates, and error details.
- Audit events explicitly link the acquisition workflow to stored results.

### 4.2 Fully Agentic LangGraph Workflow
- Real Phase 2 graph exists (no Phase 0/1 shells).
- Graph covers: `ingest` → `normalize` → `compliance` → `dedupe` → `extraction` → `enrichment` → `scoring` → `risk_review` → `draft_assembly` → `export_package`.
- Each node has typed state (Pydantic) and single-responsibility business logic.
- Workflow state carries IDs and workflow metadata; durable facts and artifacts are persisted in DuckDB.
- Workflow state is checkpointed and durable enough to resume interrupted runs without creating a second product-state store.

### 4.3 Agent Prompting Standard (RCTCO)
- Prompt files exist in versioned locations (`src/biradar/agents/prompts/`).
- All prompts strictly follow the **RCTCO** structure: Role, Core Task, Context, Constraints, Output Format.
- Constraints explicitly cover evidence rules, uncertainty handling, and prohibited behaviors (e.g., "Do not decide publishability," "Mark unsupported claims explicitly").
- Output formats are strictly structured (JSON schema) for downstream consumption.

### 4.4 Structured Extraction & Free/Public Enrichment
- Extraction agent returns structured filing facts with per-field confidence scores.
- Raw source links and evidence snippets are preserved in `evidence_items`.
- Enrichment uses strictly defined official/free sources: `unternehmensregister.de`, public `handelsregister.de` views, and the inferred company website. **Rule:** If an HTTP 403 or Cloudflare challenge is encountered, the agent must mark the enrichment as `blocked_by_anti_bot`, halt retries, and proceed with lower confidence.
- Every enrichment claim has an evidence link or is explicitly marked as inference.
- Enrichment failures degrade gracefully without blocking the entire run, unless explicitly required by policy.

### 4.5 Deterministic Guardrails
- Compliance filtering (corporate-only) is code-owned, not prompt-owned.
- Deduplication logic is deterministic and idempotent.
- Score calculation uses the deterministic weighted formula. The Research Analyst Agent proposes the 1–5 dimension scores and rationale. The deterministic `scoring` module validates these are within bounds, applies weights from `config/scoring.yaml`, and auto-approves them. If aggregate confidence is below threshold, the candidate is automatically quarantined.
- Quarantine and threshold rules are enforced in code.
- Export gates block records that fail evidence, status, or confidence requirements.

### 4.6 Autonomous Ranking, Risk Review & Export
- Agents propose ranked candidates without manual scoring input.
- Risk-review nodes automatically block drafts containing unsupported claims, financial-advice language, or personal-data leakage. **Self-Correction Loop:** The Risk Review agent can send structured feedback back to the Analyst/Extraction Agent for a maximum of 2 retries. If it fails twice, the candidate is auto-quarantined, excluded from the export package, and persisted with an explicit audit-visible reason to prevent workflow deadlocks.
- Workflow strictly separates facts, inference, and editorial text.
- Exported package includes: Markdown draft, structured JSON, run/audit summary, disclaimer, evidence traceability, and candidate confidence context.

### 4.7 Scheduled Runs & MCP Surface
- A runnable local command or scheduler entrypoint exists for the full Phase 2 workflow.
- Runs can execute repeatedly without manual cleanup; interrupted runs resume or fail cleanly with visible state.
- MCP exposes the Phase 2 workflow safely (queue inspection, source-run history, candidate detail, export package retrieval).
- Tool outputs remain stable envelopes; Phase 2 tools do not publish externally.
- Phase 2 operator surfaces remain local-only; no outbound alerts, chat notifications, or subscriber delivery are introduced in this phase.

### 4.8 Test & Eval Coverage
- Unit tests cover all deterministic business rules (compliance, dedupe, scoring).
- Integration tests cover repository and `source_run` behavior.
- Workflow tests cover LangGraph orchestration and state transitions.
- E2E tests cover the path from fresh scrape fixture to exported artifact.
- LLM evals cover extraction accuracy, risk-review blocking, and unsupported-claim handling.

---

## 5. Architecture & Workflow Design

### 5.1 LangGraph State Model
The workflow state is strongly typed and checkpointed for restart safety, while DuckDB remains the single durable product-state store. Graph state should carry record IDs, workflow metadata, and transient node outputs only. Raw records, candidate rows, evidence items, scores, reviews, and exported artifacts belong in `data/radar.duckdb`.

```python
class Phase2WorkflowState(TypedDict):
    source_run_id: str
    raw_record_ids: list[str]
    candidate_ids: list[str]
    extraction_result_ids: list[str]
    enrichment_result_ids: list[str]
    score_ids: list[str]
    risk_review_ids: list[str]
    issue_id: str | None
    export_path: str | None
    current_step: str
    retry_counts: dict[str, int]
    errors: list[str]
    warnings: list[str]
```

### 5.2 Persistence Mapping For Agent Outputs
The ID-based graph state must map to explicit persisted records so workflow resume, audit, and operator inspection remain reliable:

- `raw_record_ids` -> `raw_records`
- `candidate_ids` -> `candidates`
- `extraction_result_ids` -> persisted structured extraction records, either as dedicated repository-backed extraction tables or as normalized candidate/evidence writes with stable IDs
- `enrichment_result_ids` -> persisted enrichment/evidence records, either as dedicated repository-backed enrichment tables or as normalized evidence writes with stable IDs
- `score_ids` -> `scores`
- `risk_review_ids` -> persisted review/risk-review records, either by extending `reviews` with machine-review metadata or by adding a dedicated repository-backed risk-review table
- `issue_id` -> `issues` and `issue_candidates`

Whichever persistence shape is chosen, it must be explicitly modeled in migrations and repository APIs before workflow implementation begins. Agent outputs may not live only in checkpoint state.

### 5.3 Agentic Nodes (RCTCO Prompts)
1. **Extraction Agent:** Extracts company name, legal form, court, case number, filing date, administrator, proceeding stage, and sector hints.
2. **Enrichment Agent:** Searches free/public sources for company scale, sector, assets, and operating status. Cites sources or marks as inference.
3. **Research Analyst Agent:** Writes a short opportunity thesis, buyer-fit tags, and identifies missing information.
4. **Risk Review Agent:** Detects unsupported claims, financial-advice language, defamatory wording, and personal-data leakage. **Blocks** drafts that fail.

### 5.4 Deterministic Guardrails (Code-Owned)
- `biradar.domain.compliance`: Regex/allowlist for legal forms (GmbH, AG, UG, KG, OHG, etc.). Rejects consumer/personal filings.
- `biradar.domain.dedupe`: Canonical key generation (normalized name + court + case number + publication date).
- `biradar.domain.scoring`: Pure function applying weights from `config/scoring.yaml`.
- `biradar.domain.export_gates`: Validates that all included candidates have `status == "publish_ready"`, approved scores, and sufficient evidence before allowing Markdown/JSON generation.

---

## 6. Task Breakdown (Atomic & Verifiable)

### Task 1: Official Source Adapter & Observability
- [ ] Implement `src/biradar/sources/official_portal.py` with robust JSF portal scraping logic. The adapter must explicitly manage JSF session state, extract and replay `javax.faces.ViewState` and hidden CSRF tokens, and implement realistic delays/headers to avoid anti-bot blocking.
- [ ] Add robust HTTP retries, timeouts, and structured error parsing.
- [ ] Implement `source_run` creation at the start and end of every scrape attempt.
- [ ] Write unit tests for parse logic, date normalization, and empty-result handling.
- [ ] Write integration test verifying idempotency over the same date window.

### Task 2: LangGraph Workflow Orchestration
- [ ] Define `Phase2WorkflowState` in `src/biradar/graph/state.py`.
- [ ] Finalize the persistence model for extraction, enrichment, and risk-review outputs, including any required DuckDB migrations and repository methods, before wiring graph nodes that reference those IDs.
- [ ] Implement persistent checkpointing in `src/biradar/graph/checkpoints.py` so workflow state survives process crashes or scheduled interruptions, while keeping DuckDB as the single durable store for product facts and exported artifacts.
- [ ] Wire the graph: `ingest` → `normalize` → `compliance` → `dedupe` → `extraction` → `enrichment` → `scoring` → `risk_review` → `draft_assembly` → `export`.
- [ ] Keep graph state limited to IDs, workflow metadata, and transient node outputs; persist durable facts through repository-layer writes.
- [ ] Write workflow unit tests for each node's state transformation.

### Task 3: RCTCO Prompting & Structured Extraction
- [ ] Create prompt files in `src/biradar/agents/prompts/` for Extraction, Enrichment, Analyst, and Risk Review.
- [ ] Enforce RCTCO structure with explicit constraints on evidence and uncertainty.
- [ ] Implement Pydantic models for structured outputs with per-field confidence.
- [ ] Add explicit anti-bot handling to enrichment contracts: when a free/public source returns HTTP 403, Cloudflare, or similar bot-block signals, mark the attempt as `blocked_by_anti_bot`, stop retries for that source, and continue with lower confidence.
- [ ] Write LLM eval tests using golden fixtures to verify extraction accuracy and unsupported-claim marking.

### Task 4: Deterministic Guardrails & Scoring
- [ ] Finalize `biradar.domain.compliance` allowlist and quarantine logic.
- [ ] Implement `biradar.domain.dedupe` as a deterministic rule set: canonical exact key matching first, followed by explicitly defined secondary matching rules with fixed normalization and thresholds. No nondeterministic or model-owned dedupe decisions are allowed.
- [ ] Implement `biradar.domain.scoring` pure function reading from `config/scoring.yaml`.
- [ ] Write unit tests for all guardrail modules with edge-case fixtures (e.g., sole proprietor, ambiguous legal form).

### Task 5: Autonomous Ranking & Risk Review
- [ ] Implement ranking logic sorting candidates by approved score and editorial rules.
- [ ] Implement Risk Review node to actively reject drafts with policy violations (returning to a "quarantined" or "needs_revision" state, or dropping the candidate from the draft).
- [ ] Persist every risk-review failure, retry, quarantine, and exclusion reason in audit-friendly storage and expose it through operator surfaces; failed candidates may be excluded from export, but never silently.
- [ ] Ensure facts, inferences, and editorial text are distinctly tagged in the state.

### Task 6: Export-Ready Local Artifact Package
- [ ] Implement `biradar.output.markdown` and `biradar.output.json` generators.
- [ ] Ensure generated artifacts include: disclaimer, evidence traceability links, and candidate confidence context.
- [ ] Write test verifying that unapproved/quarantined candidates are excluded from the export package.
- [ ] Write test verifying no external network calls are made during export.

### Task 7: Scheduling & MCP Surface
- [ ] Create `biradar.cli.phase2_run` command for local execution.
- [ ] Implement MCP tools for the Phase 2 local workflow and operator surface, aligned with the documented interface: `radar_run_phase2_workflow`, `radar_list_source_runs`, candidate detail inspection, and export package retrieval.
- [ ] Write MCP contract tests ensuring stable result envelopes and no external publish actions.
- [ ] Verify no outbound notification, chat, email, webhook, or subscriber delivery path is active in Phase 2.
- [ ] Document how to disable legacy `insolvency-scout` cron/launchd jobs.

### Task 8: Testing & Eval Coverage
- [ ] Assemble golden fixtures: GmbH, UG, GmbH & Co. KG, individual debtor (must quarantine), duplicate records, malformed source, and enrichment anti-bot/403 cases.
- [ ] Achieve >80% coverage on deterministic domain modules.
- [ ] Run full E2E acceptance test from a saved HTML fixture of the official portal to a validated local export package.
- [ ] Add contract and negative tests proving `blocked_by_anti_bot` handling, deterministic dedupe stability, and absence of outbound notification/publish paths.
- [ ] Update `docs/phase-2-verification-checklist.md` with actual verification results.

---

## 7. Risk Mitigation & Boundaries

| Risk | Mitigation Strategy |
|------|---------------------|
| **Portal JSF changes break scraper** | Structured parse errors are caught, logged in `source_run`, and fail gracefully without corrupting state. Alert via health check. |
| **Agent hallucinates financial advice** | Risk Review agent explicitly scans for prohibited language. Deterministic export gates block any draft that fails this check. |
| **Enrichment source blocks or rate limits access** | Enrichment is free/public only. HTTP 403, Cloudflare, and similar anti-bot signals are recorded as `blocked_by_anti_bot`, retries stop for that source, and the candidate proceeds with lower confidence or is quarantined if evidence is insufficient. |
| **Duplicate candidates pollute output** | Deterministic dedupe keys (normalized name + court + case number + date) are applied *before* any agentic processing. |
| **Split durable state between graph checkpoints and product storage** | Keep workflow checkpoints lightweight and ID-based. DuckDB remains the single durable store for facts, evidence, scores, reviews, and export artifacts. |
| **Accidental external publishing or outbound delivery** | No beehiiv, email, Telegram, webhook, or alert code paths exist in the Phase 2 codebase. Export writes strictly to `data/exports/`. |

---

## 8. Verification & Sign-off Procedure

Before marking Phase 2 as complete, execute the following manual and automated verification steps:

1. **Disable Legacy:** Verify `insolvency-scout` cron/launchd jobs are disabled.
2. **Run E2E Test:** Execute `make test-e2e-phase2` to run the full pipeline against golden fixtures.
3. **Run Live Dry-Run:** Execute `biradar run-phase2 --dates 2026-06-10:2026-06-16 --dry-run` to verify portal connectivity and idempotency.
4. **Run Live Execution:** Execute `biradar run-phase2 --dates 2026-06-10:2026-06-16` and verify:
   - A `source_run` is created.
   - Candidates are deduped and compliant.
   - Agents extract and enrich with evidence links.
   - Free/public-source anti-bot blocks are recorded as `blocked_by_anti_bot` and do not deadlock the run.
   - Scores are calculated deterministically.
   - Risk review passes or quarantines appropriately.
   - An export package is generated in `data/exports/`.
5. **Audit Review:** Call `radar_audit_trail` for a generated candidate to verify full lineage from raw record to export.
6. **Operator Surface Review:** Verify MCP/CLI surfaces expose local run control, source-run history, candidate detail, audit trail, and export retrieval without any outbound notification or publishing behavior.
7. **Checklist Update:** Review and check off all items in `docs/phase-2-verification-checklist.md`.

---

## 9. Next Steps for Review

1. Review this plan for alignment with business and legal constraints.
2. Approve the task breakdown and RCTCO prompting strategy.
3. Upon approval, begin execution starting with **Task 1: Official Source Adapter & Observability**.
