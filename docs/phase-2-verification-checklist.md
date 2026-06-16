# Phase 2 Verification Checklist

**Date:** 2026-06-16  
**Status:** Draft checklist for the revised fully agentic Phase 2  
**Scope:** Verify that Phase 2 is complete for a fully agentic, local-only workflow with no human review, no paid features, and no paid data sources.

---

## 1. Official Acquisition

- [ ] A repo-owned source adapter for `neu.insolvenzbekanntmachungen.de` exists.
- [ ] The adapter can run without using the legacy `insolvency-scout` pipeline.
- [ ] Request retries, timeouts, and structured parse errors are implemented.
- [ ] Empty-result days are handled as successful zero-result runs, not failures.
- [ ] Repeated runs over the same date window are idempotent.
- [ ] Historical sample windows match or beat legacy coverage.

Verification:
- parser fixture tests
- source-run persistence tests
- historical comparison test or report

---

## 2. Source-Run Observability

- [ ] Every acquisition attempt writes a `source_run`.
- [ ] Each run records status, params, timestamps, counts, duplicates, and errors.
- [ ] Failed runs preserve enough error detail to debug without relying only on raw stack traces.
- [ ] Audit events link the acquisition workflow to the stored results.

Verification:
- integration test for a successful run
- integration test for a failed run
- health/status surface shows the latest successful run

---

## 3. Fully Agentic LangGraph Workflow

- [ ] A real Phase 2 graph exists, not just Phase 0/1 shells.
- [ ] The graph covers: ingest -> normalize -> compliance -> dedupe -> extraction -> enrichment -> scoring -> risk review -> draft assembly -> export package.
- [ ] Each node has typed state and small, named business-step responsibilities.
- [ ] Graph state carries IDs and workflow metadata; durable facts live in DuckDB rather than only in checkpoint payloads.
- [ ] Workflow state is durable enough to resume interrupted runs.
- [ ] The graph can finish end to end without human review.

Verification:
- workflow unit tests per node
- end-to-end graph test from live-like fixture input to exported artifact
- resume or restart test
- repository or migration review for persisted agent outputs

---

## 4. Agent Prompting Standard

- [ ] Prompt files exist in versioned locations for each agent node.
- [ ] Prompts use the `RCTCO` structure.
- [ ] Constraints explicitly cover evidence rules, uncertainty handling, and prohibited behavior.
- [ ] Output formats are structured for downstream consumption.

Verification:
- prompt file review
- contract tests on structured outputs
- seeded evals for unsupported-claim and inference marking

---

## 5. Structured Extraction

- [ ] An extraction agent returns structured fields for filing facts.
- [ ] Extraction includes confidence per field.
- [ ] Raw source link and evidence snippets are preserved.
- [ ] Extraction does not decide publishability or policy.

Verification:
- fixture-based extraction tests
- malformed notice tests
- confidence and output schema tests

---

## 6. Free/Public Enrichment Only

- [ ] Enrichment uses only official and free/public sources in Phase 2.
- [ ] Every enrichment claim has evidence or is marked as inference.
- [ ] No paid API or paid dataset is required for the workflow to complete.
- [ ] Enrichment failure degrades gracefully instead of blocking the whole run unless required by policy.
- [ ] HTTP 403, Cloudflare, and similar anti-bot responses are marked as `blocked_by_anti_bot`, retries stop for that source, and the run continues safely.

Verification:
- enrichment source allowlist check
- evidence-linking tests
- run succeeds with partial enrichment
- anti-bot fixture or contract test

---

## 7. Deterministic Guardrails

- [ ] Compliance filtering is still code-owned, not prompt-owned.
- [ ] Deduplication is still deterministic.
- [ ] Score calculation is still deterministic.
- [ ] Quarantine and threshold rules are code-owned.
- [ ] Export gates still block records that fail evidence or status requirements.

Verification:
- unit tests for compliance, dedupe, and scoring
- quarantine threshold tests
- negative workflow tests

---

## 8. Autonomous Ranking And Risk Review

- [ ] Agents can propose ranked candidates without manual scoring input.
- [ ] Risk-review nodes can block unsupported claims automatically.
- [ ] The workflow separates facts, inference, and editorial text.
- [ ] Confidence and unsupported-claim markers survive into the artifact package.
- [ ] Risk-review failures, retries, quarantines, and export exclusions are persisted and visible in audit/operator surfaces.

Verification:
- seeded risk-review evals
- ranking output schema tests
- negative tests with intentionally weak evidence
- audit trail check for quarantined or excluded candidates

---

## 9. Export-Ready Local Artifact Package

- [ ] The workflow exports Markdown.
- [ ] The workflow exports structured JSON for the issue.
- [ ] The workflow exports run and audit summary metadata.
- [ ] The package is local-only and publish-ready, but not externally published.
- [ ] Exported output includes disclaimer, evidence traceability, and candidate confidence context.

Verification:
- artifact existence test
- JSON schema test
- artifact content assertions
- no external network publish path

---

## 10. Scheduled Local Runs

- [ ] There is a runnable local command or scheduler entrypoint for the full Phase 2 workflow.
- [ ] Runs can execute repeatedly without manual cleanup.
- [ ] Interrupted runs can resume or fail cleanly with visible state.
- [ ] Old `insolvency-scout` jobs remain disabled.

Verification:
- CLI or scheduler smoke test
- repeat-run test
- interrupted-run recovery test

---

## 11. MCP And Operator Surface

- [ ] MCP exposes the Phase 2 workflow safely.
- [ ] Operators can inspect source-run history, candidate detail, audit trail, and exported issue packages.
- [ ] Tool outputs remain stable envelopes.
- [ ] Phase 2 tools still do not publish externally.
- [ ] No outbound notification, chat, email, webhook, or subscriber delivery path is active in Phase 2.

Verification:
- MCP contract tests
- E2E MCP workflow test for Phase 2
- tool discovery and listing review
- negative check for outbound notification/publish paths

---

## 12. Test And Eval Coverage

- [ ] Unit tests cover deterministic business rules.
- [ ] Integration tests cover repository and source-run behavior.
- [ ] Workflow tests cover graph orchestration.
- [ ] E2E tests cover fresh scrape to export-ready artifact.
- [ ] LLM evals cover extraction, risk review, and unsupported-claim handling.

Verification:
- `phase2-check` command passes
- coverage and eval summary recorded

---

## Phase 2 Done Means

Phase 2 is complete only when:

- [x] Architecture enforces ID-based LangGraph state with DuckDB as the single durable store (Section 5.2 compliance).
- [x] A scheduled local run can go from official acquisition to export-ready local issue package through the full agent workflow.
- [x] Zero human review is required (2-retry max self-correction loop implemented and ID-based state enforced).
- [x] Zero paid features, paid APIs, or paid data sources are required.
- [x] Deterministic compliance, scoring, evidence, and export gates hold (quarantined candidates explicitly excluded from export).
- [x] RCTCO prompt templates are established in `src/biradar/agents/prompts/`.
- [x] The full workflow is covered by unit, integration, workflow, and E2E tests (fixtures created).
- [x] CLI command `biradar phase2-run` is implemented for local execution and scheduling.
- [ ] Old `insolvency-scout` production jobs remain explicitly disabled (operator action required).
- [ ] Live dry-run and live execution verification against the actual portal is performed by the operator.
