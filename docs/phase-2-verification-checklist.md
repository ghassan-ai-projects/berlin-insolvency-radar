# Phase 2 Verification Checklist

**Date:** 2026-06-16  
**Status:** Locally verified implementation with remaining live-environment and operator gates  
**Scope:** Verify that Phase 2 is complete for a fully agentic, local-only workflow with no human review, no paid features, and no paid data sources.

---

## 1. Official Acquisition

- [x] A repo-owned source adapter for `neu.insolvenzbekanntmachungen.de` exists.
- [x] The adapter can run without using the legacy `insolvency-scout` pipeline.
- [x] Request retries, timeouts, and structured parse errors are implemented.
- [x] Empty-result days are handled as successful zero-result runs, not failures.
- [x] Repeated runs over the same date window are idempotent for raw-record and candidate persistence in fixture-backed verification.
- [ ] Historical sample windows match or beat legacy coverage.

Verification:
- parser fixture tests
- source-run persistence tests
- historical comparison test or report

---

## 2. Source-Run Observability

- [x] Every acquisition attempt writes a `source_run`.
- [x] Each run records status, params, timestamps, counts, duplicates, and errors.
- [x] Failed runs preserve enough error detail to debug without relying only on raw stack traces.
- [x] Audit events link the acquisition workflow to the stored results.

Verification:
- integration test for a successful run
- integration test for a failed run
- health/status surface shows the latest successful run

---

## 3. Fully Agentic LangGraph Workflow

- [x] A real Phase 2 graph exists, not just Phase 0/1 shells.
- [x] The graph covers: ingest -> normalize -> compliance -> dedupe -> extraction -> enrichment -> scoring -> risk review -> draft assembly -> export package.
- [x] Each node has typed state and small, named business-step responsibilities.
- [x] Durable facts live in DuckDB rather than only in checkpoint payloads; graph state carries workflow metadata plus transient execution state for the active run.
- [ ] Workflow state is durable enough to resume interrupted runs.
- [x] The graph can finish end to end without human review.

Verification:
- workflow unit tests per node
- end-to-end graph test from live-like fixture input to exported artifact
- resume or restart test
- repository or migration review for persisted agent outputs

---

## 4. Agent Prompting Standard

- [x] Prompt files exist in versioned locations for each agent node.
- [x] Prompts use the `RCTCO` structure.
- [x] Constraints explicitly cover evidence rules, uncertainty handling, and prohibited behavior.
- [x] Output formats are structured for downstream consumption.

Verification:
- prompt file review
- contract tests on structured outputs
- seeded evals for unsupported-claim and inference marking

---

## 5. Structured Extraction

- [x] An extraction agent returns structured fields for filing facts.
- [x] Extraction includes confidence per field.
- [x] Raw source link and evidence snippets are preserved.
- [x] Extraction does not decide publishability or policy.

Verification:
- fixture-based extraction tests
- malformed notice tests
- confidence and output schema tests

---

## 6. Free/Public Enrichment Only

- [x] Enrichment uses only official and free/public sources in Phase 2.
- [x] Every enrichment claim has evidence or is marked as inference.
- [x] No paid API or paid dataset is required for the workflow to complete.
- [x] Enrichment failure degrades gracefully instead of blocking the whole run unless required by policy.
- [x] HTTP 403, Cloudflare, and similar anti-bot responses are marked as `blocked_by_anti_bot`, retries stop for that source, and the run continues safely.

Verification:
- enrichment source allowlist check
- evidence-linking tests
- run succeeds with partial enrichment
- anti-bot fixture or contract test

---

## 7. Deterministic Guardrails

- [x] Compliance filtering is still code-owned, not prompt-owned.
- [x] Deduplication is still deterministic.
- [x] Score calculation is still deterministic.
- [x] Quarantine and threshold rules are code-owned.
- [x] Export gates still block records that fail evidence or status requirements.

Verification:
- unit tests for compliance, dedupe, and scoring
- quarantine threshold tests
- negative workflow tests

---

## 8. Autonomous Ranking And Risk Review

- [x] Agents can propose ranked candidates without manual scoring input.
- [x] Risk-review nodes can block unsupported claims automatically.
- [x] The workflow separates facts, inference, and editorial text.
- [x] Confidence and unsupported-claim markers survive into the artifact package.
- [x] Risk-review failures, retries, quarantines, and export exclusions are persisted and visible in audit/operator surfaces.

Verification:
- seeded risk-review evals
- ranking output schema tests
- negative tests with intentionally weak evidence
- audit trail check for quarantined or excluded candidates

---

## 9. Export-Ready Local Artifact Package

- [x] The workflow exports Markdown.
- [x] The workflow exports structured JSON for the issue.
- [x] The workflow exports run and audit summary metadata.
- [x] The package is local-only and publish-ready, but not externally published.
- [x] Exported output includes disclaimer, evidence traceability, and candidate confidence context.

Verification:
- artifact existence test
- JSON schema test
- artifact content assertions
- no external network publish path

---

## 10. Scheduled Local Runs

- [x] There is a runnable local command or scheduler entrypoint for the full Phase 2 workflow.
- [x] Runs can execute repeatedly without manual cleanup.
- [ ] Interrupted runs can resume or fail cleanly with visible state.
- [ ] Old `insolvency-scout` jobs remain disabled.

Verification:
- CLI or scheduler smoke test
- repeat-run test
- interrupted-run recovery test

---

## 11. MCP And Operator Surface

- [x] MCP exposes the Phase 2 workflow safely.
- [x] Operators can inspect source-run history, candidate detail, audit trail, and exported issue packages.
- [x] Tool outputs remain stable envelopes.
- [x] Phase 2 tools still do not publish externally.
- [x] No outbound notification, chat, email, webhook, or subscriber delivery path is active in Phase 2.

Verification:
- MCP contract tests
- E2E MCP workflow test for Phase 2
- tool discovery and listing review
- negative check for outbound notification/publish paths

---

## 12. Test And Eval Coverage

- [x] Unit tests cover deterministic business rules.
- [x] Integration tests cover repository and source-run behavior.
- [x] Workflow tests cover graph orchestration.
- [x] E2E tests cover fresh scrape to export-ready artifact.
- [ ] LLM evals cover extraction, risk review, and unsupported-claim handling.

Verification:
- [x] `phase2-check` command passes
- [x] Coverage summary recorded (`uv run pytest` -> `54 passed`, overall coverage `87%`)
- [ ] Eval summary recorded

---

## Phase 2 Done Means

Phase 2 is complete only when:

- [x] Durable product state is persisted in DuckDB and the workflow is locally verified end to end with fixture-backed acquisition.
- [x] A scheduled local run can go from official acquisition to export-ready local issue package through the full agent workflow.
- [x] Zero human review is required (2-retry max self-correction loop implemented and ID-based state enforced).
- [x] Zero paid features, paid APIs, or paid data sources are required.
- [x] Deterministic compliance, scoring, evidence, and export gates hold (quarantined candidates explicitly excluded from export).
- [x] RCTCO prompt templates are established in `src/biradar/agents/prompts/`.
- [x] The full workflow is covered by unit, integration, workflow, and E2E tests (fixtures created).
- [x] CLI command `biradar phase2-run` is implemented for local execution and scheduling.
- [x] CLI command `biradar phase2-check` passes for fixture-backed persisted local verification.
- [ ] Old `insolvency-scout` production jobs remain explicitly disabled (operator action required).
- [ ] Live dry-run and live execution verification against the actual portal is performed by the operator.
