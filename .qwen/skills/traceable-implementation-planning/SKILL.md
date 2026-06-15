---
name: traceable-implementation-planning
description: Procedure for creating a traceable, gap-driven implementation plan by comparing project docs (acceptance tests, architecture) against current code state.
source: auto-skill
extracted_at: '2026-06-15T17:18:00.000Z'
---

# Traceable Implementation Planning

When tasked with planning the next phase of a project, do not generate a generic to-do list. Instead, build a **traceable, gap-driven implementation plan** by cross-referencing authoritative project documentation (acceptance tests, architecture docs, strategy) with the actual current code state.

## 1. Discovery & Context Gathering
Before planning, read all relevant context:
- **Acceptance Criteria**: `docs/strategy/phase-acceptance-tests.md` (what "done" means).
- **Architecture**: `docs/strategy/application-architecture.md` (how it should be built).
- **Previous Reviews**: `docs/phase-0-review.md` or `phase-0-plan-traceability.md` (known gaps and technical debt).
- **Current Code**: Inspect `src/` services, repositories, domain logic, and `tests/` coverage to verify what is actually implemented vs. scaffolding.

## 2. Gap Analysis Matrix
Create a table mapping the current state to the Phase requirements. Identify specific deficiencies:
| Gap Area | Current State | Phase Requirement |
|---|---|---|
| e.g., Legacy Import | Simulates mapping counts; `inserted = 0` | Real idempotent upsert with pre/post hash verification |
| e.g., Repository Pattern | Direct ad-hoc SQL in Services | All DuckDB access flows through explicit Repository classes |

## 3. Define Explicit Out-of-Scope Boundaries
Prevent scope creep by explicitly listing what will **not** be built in this phase (e.g., live scraping, external publishing, autonomous LLM scoring). This keeps the plan focused on the core workflow.

## 4. Step-by-Step Implementation Tasks
Break the work into discrete, sequential tasks. Each task must:
- Have a clear objective.
- Directly close one or more gaps identified in the matrix.
- Specify the files/modules to be created or modified.
- Include a micro-acceptance criterion (e.g., "No ad-hoc SQL outside `storage/`").

## 5. Testing Strategy Alignment
Explicitly map testing requirements to the plan:
- **Unit**: Deterministic domain modules (compliance, scoring, dedupe).
- **Integration**: Service layer with temporary databases.
- **Fixtures**: Define required golden fixtures (e.g., valid GmbH, rejected consumer, duplicate records).

## 6. Definition of Done (DoD)
The plan must conclude with a strict, verifiable DoD section containing:
- **Automated Gates**: Exact `make` or `uv run` commands that must pass (e.g., `uv run make test-integration`).
- **Manual Verification Script**: A step-by-step sequence (e.g., health → import → list → review → draft → export → audit) that a human can run to prove end-to-end functionality.
- **Safety & Compliance Checks**: Explicit confirmations (e.g., "Legacy DB hash unchanged", "No external API calls active").

## 7. Completeness Review
Before finalizing the plan document, perform a self-review:
- Does every task map to a specific Acceptance Test (e.g., AT-1.x)?
- Does the plan respect the architecture principles (e.g., "Agents suggest, code verifies")?
- Are all known Phase 0 gaps explicitly addressed?

## Output Format
Write the final plan to `docs/strategy/phase-X-implementation-plan.md` using clear Markdown headings, tables for gap analysis, and checklists for the Definition of Done.
