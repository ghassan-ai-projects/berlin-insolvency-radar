---
name: agentic-pipeline-architecture-constraints
description: Strict architectural constraints for building fully agentic, zero-human-intervention workflows to prevent deadlocks, state loss, and scraping failures.
source: auto-skill
extracted_at: '2026-06-16T08:19:41.385Z'
---

# Agentic Pipeline Architecture Constraints

When designing or implementing a fully agentic, zero-human-intervention workflow (e.g., Phase 2+ autonomous pipelines), enforce the following hard boundaries to prevent deadlocks, silent failures, and data corruption.

## 1. Prevent Agentic Deadlocks (Self-Correction Limits)
Autonomous loops without exit conditions will deadlock the pipeline.
- **Rule:** Any agentic self-correction or revision loop (e.g., Risk Review sending feedback to Extraction/Analyst) must have a strict maximum retry limit (e.g., 2 retries).
- **Fallback:** If the limit is exceeded, the agent must auto-quarantine the entity and silently drop it from the final export package. Do not wait for human input.

## 2. Deterministic Scoring Validation
LLMs cannot be trusted to enforce mathematical or policy boundaries on their own.
- **Rule:** The LLM/Agent may only *propose* dimension scores (e.g., 1–5) and rationale.
- **Fallback:** A deterministic, code-owned scoring module must validate that all proposed scores are within strict bounds, apply the weighted formula from configuration (e.g., `config/scoring.yaml`), and auto-approve. If aggregate confidence is below a defined threshold, the candidate is automatically quarantined.

## 3. Robust JSF/Complex Portal Scraping
Naive HTTP requests to JavaServer Faces (JSF) or heavily protected portals will fail immediately.
- **Rule:** The source adapter must explicitly manage session state. This includes extracting and replaying `javax.faces.ViewState`, hidden CSRF tokens, and maintaining cookies.
- **Parsing Rule:** JSF partial responses are typically XML wrapping CDATA-containing HTML. Use `xml.etree.ElementTree` to find `<update id="...">` tags, then parse the inner CDATA with `BeautifulSoup` to extract tabular data safely.
- **Fallback:** Implement realistic async delays (`asyncio.sleep`), standard browser headers, and structured error parsing to avoid anti-bot blocking. Failures must be logged in a `source_run` record, not raised as unhandled exceptions.

## 4. Strict Enrichment Allowlists & Anti-Bot Fallback
Agents will hallucinate sources or get stuck in infinite retry loops on protected sites.
- **Rule:** Define an explicit, hardcoded allowlist of free/public sources (e.g., `unternehmensregister.de`, public `handelsregister.de` views, inferred company website).
- **Fallback:** If an HTTP 403, 503, or Cloudflare challenge is encountered, the agent must immediately mark the enrichment status as `blocked_by_anti_bot`, halt all retries for that source, and proceed with the pipeline using a lower confidence score. 

## 5. Persistent Workflow Checkpointing
In-memory state is lost on process crashes, breaking scheduled runs and idempotency.
- **Rule:** LangGraph (or equivalent orchestration framework) must use a persistent checkpointing backend.
- **Implementation:** Use `SqliteSaver` or a custom DuckDB-backed saver. In-memory checkpointing is strictly unacceptable for any scheduled or production agentic workflow.

## 6. Completion Notification Hooks
Zero-intervention pipelines require out-of-band signaling for success or critical failure.
- **Rule:** Implement a dedicated notification hook (e.g., `radar_notify_completion` MCP tool or CLI hook).
- **Implementation:** Trigger this hook via native integrations (e.g., OpenClaw's Telegram integration) upon successful end-to-end run completion or hard pipeline failure, ensuring the operator is alerted without polling.

## 7. LangGraph State & MCP Envelope Standards
Agentic workflows must maintain strict boundaries between orchestration state and persistent storage.
- **Rule:** LangGraph `State` (e.g., `Phase2WorkflowState`) should only carry workflow metadata, IDs, and transient retry counters (e.g., `risk_review_retries: dict[str, int]`). 
- **Implementation:** Durable facts (candidates, scores, evidence) must be written to the database (DuckDB/Postgres) *within* the node execution, not just held in the graph state. MCP tools must return stable `ResultEnvelope` objects (`ok`, `data`, `errors`, `next_action`) to ensure predictable agent consumption.

## Review Checklist
Before approving an agentic workflow design, verify:
- [ ] All retry loops have a hard numeric limit and a quarantine fallback.
- [ ] LLM outputs feeding deterministic logic are validated for type and range bounds.
- [ ] Scrapers handle session state (ViewState/CSRF) and anti-bot evasion.
- [ ] Enrichment has explicit allowlists and `blocked_by_anti_bot` fallbacks.
- [ ] Checkpointing is persisted to disk (SQLite/DuckDB), not memory.
- [ ] A completion notification mechanism is defined and implemented.
- [ ] LangGraph state only holds transient metadata; durable facts are persisted to the DB within nodes.
- [ ] MCP tools return stable, typed result envelopes.