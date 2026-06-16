---
name: langgraph-agentic-pipeline-implementation
description: Best practices and critical pitfalls to avoid when implementing LangGraph agentic workflows, focusing on state management, persistence, and loop logic.
source: auto-skill
extracted_at: '2026-06-16T08:52:35.883Z'
---

# LangGraph Agentic Pipeline Implementation Guide

When building fully agentic, zero-human-intervention LangGraph workflows, strict adherence to state management, persistence boundaries, and loop logic is required to prevent deadlocks, data loss, and silent failures.

## 1. State Management & Persistence Boundaries
- **ID-Based State Only**: The LangGraph `State` (e.g., `TypedDict`) must carry **only IDs, workflow metadata, and transient node outputs**. 
- **Durable Facts in DB**: Never store full dictionaries or large payloads (e.g., `candidates: list[dict]`) in the graph state. Persist durable facts (candidates, evidence, scores, reviews) to the repository layer (e.g., DuckDB) and store only their `*_ids` in the state.
- **Immutability**: Always return a **new state dictionary** to ensure proper LangGraph checkpointing and diffing. 
  - ❌ Bad: `state["warnings"].append("msg"); return state`
  - ✅ Good: `return {**state, "warnings": state.get("warnings", []) + ["msg"]}`

## 2. Loop & Conditional Routing Logic
- **No Early Returns in Batch Loops**: When evaluating multiple items (e.g., candidates in a risk-review node), the loop must process **all** items before evaluating the retry/exit condition. An early `return state` inside the loop will skip remaining items, causing silent data loss.
  - ✅ Pattern: Collect all items needing retry in a boolean flag or list during the loop. Evaluate the flag *after* the loop completes to decide the next step.
- **Conditional Edge State Key Alignment**: Ensure the conditional router checks the *exact* state key that the preceding node updates. If a node updates `state["current_step"]`, the router must check `state.get("current_step")`, not `state["status"]`. Mismatches here silently break retry loops.

## 3. Connection Lifecycle Management
- **Long-Lived Connections**: For persistent checkpointing (e.g., `SqliteSaver`), manage the database connection at the **application lifecycle level** (e.g., in `AppContainer`). 
- **Avoid Short-Lived Context Managers**: Do not open and close the SQLite connection in a `with` block around the saver initialization. If the compiled graph is invoked outside that block, it will crash with a "Connection closed" error.

## 4. Python, Typing & Validation Best Practices
- **Datetime**: Use `datetime.now(timezone.utc)` instead of the deprecated `datetime.utcnow()`.
- **Pydantic Attribute Access**: When accessing nested config values that might be Pydantic models, use `getattr(config.scoring.thresholds, "interesting", 2.0)` instead of `.get()`, which will raise an `AttributeError` on Pydantic V2 models.
- **Date Validation**: Use Pydantic's native `date` type (e.g., `start_date: date`) instead of regex patterns, which allow invalid calendar dates like `2026-99-99`.
- **Dry-Run Isolation**: When implementing `dry_run` flags, ensure *all* side-effecting components (including LangGraph `CheckpointManager`) are routed to in-memory backends (e.g., `:memory:`) to prevent test pollution.

## 5. Agent Prompting Standard (RCTCO) & Safe Fallbacks
All LLM nodes must use prompt files (e.g., YAML) enforcing the RCTCO structure:
- **R**ole: Expert persona.
- **C**ore Task: Primary action.
- **C**ontext: Background data.
- **C**onstraints: Explicit evidence rules, uncertainty handling, and prohibited behaviors (e.g., "Do not decide publishability").
- **O**utput: Strict JSON schema for downstream consumption.
- **Safe Fallback:** Always check for the presence of required API keys (e.g., `OPENAI_API_KEY`) before invoking the LLM. If missing, return a deterministic, safe mock result (e.g., `passed_review=True` with low confidence, or a placeholder extraction) to prevent pipeline crashes during local development or testing. Log a warning when falling back.

## 6. Self-Correction & Deadlock Prevention
- **Max Retry Limits**: Autonomous self-correction loops (e.g., Risk Review sending feedback to Extraction) must have a hard limit (e.g., 2 retries). 
- **Auto-Quarantine**: If the max retry limit is reached, the item must be auto-quarantined, excluded from final export, and the reason must be persisted to the audit/review repository to prevent workflow deadlocks.

## 7. Verification Checklist Before Merge
- [ ] Graph state contains only IDs and metadata, not full objects.
- [ ] All state mutations return a new dictionary (`{**state, ...}`).
- [ ] Batch processing loops do not contain early `return` statements.
- [ ] Conditional routing checks the exact state key updated by the preceding node.
- [ ] Database connections for checkpointing are long-lived and respect `dry_run` isolation.
- [ ] RCTCO prompt files exist for all LLM nodes.
- [ ] Unit tests actually **invoke** the node function with a mock state to verify control flow (e.g., retry increments), rather than just manually mutating a dictionary and asserting the mutation.
- [ ] Unit tests verify that quarantined/failed items are explicitly excluded from final export artifacts.