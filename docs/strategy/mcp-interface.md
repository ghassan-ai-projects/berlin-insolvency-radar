# MCP Interface

**Date:** 2026-06-15
**Status:** Proposed MCP-first product contract

---

## Principle

Berlin Insolvency Radar should be an **MCP-first intelligence service**. OpenClaw can remain the remote control, but this repo should expose the product through stable MCP tools with typed inputs, structured outputs, auditability, and safe write boundaries.

Agents should not need to know database paths, scraper internals, or newsletter file formats.

The first version should be deliberately small. An agent should be able to do the core workflow with five verbs:

```text
check
import
list/get
review
draft/export
```

The MCP layer is the public interface. CLI commands and scheduled jobs can call the same internal services.

---

## MCP v0: Keep It Tiny

The first implementation should expose only these tools:

| Tool | Purpose | Writes? |
|---|---|---:|
| `radar_health` | Is the app usable? What needs attention? | No |
| `radar_import_legacy_scout` | Import/read legacy DuckDB candidates | Yes, unless `dry_run` |
| `radar_list_candidates` | Show candidates needing work | No |
| `radar_get_candidate` | Inspect one candidate with evidence | No |
| `radar_review_candidate` | Accept/reject/mark candidate and optionally approve score | Yes |
| `radar_create_issue_draft` | Build a Markdown draft from approved candidates | Yes |
| `radar_export_issue` | Write draft to local export file | Yes |
| `radar_audit_trail` | Explain what happened | No |

Everything else in this document is v1+. The enrichment agents are now implemented (see `src/biradar/sources/enrichment.py`). Do not implement vendor bakeoff, alerts, or publishing until v0 is pleasant to use.

### Happy Path For OpenClaw

```text
1. radar_health
2. radar_import_legacy_scout { dry_run: false, since: "2026-06-01" }
3. radar_list_candidates { status: ["needs_review"], limit: 10 }
4. radar_get_candidate { candidate_id }
5. radar_review_candidate { candidate_id, decision: "approve", score: {...} }
6. radar_create_issue_draft { tier: "free", candidate_ids: [...] }
7. radar_export_issue { issue_id, format: "markdown" }
```

### One Review Tool Instead Of Many

For v0, avoid separate tools for status changes, score approval, and notes. Use one tool:

```text
radar_review_candidate
```

It can:
- approve a candidate
- reject a candidate
- request more info
- approve/override score dimensions
- add a short human/agent note

This keeps the agent loop simple and avoids forcing OpenClaw to coordinate many small state transitions.

---

## Tool Classes

| Class | Purpose | Safety |
|---|---|---|
| Health | Check app/source status | Read-only |
| Source Management | List source configs and source runs | Mostly read-only |
| Acquisition | Import/scrape candidate filings | State-changing |
| Candidate Review | Query, inspect, dedupe, approve/reject | Mixed |
| Enrichment | Add evidence and company context | State-changing |
| Scoring | Calculate and approve editorial scores | Mixed |
| Issue Drafting | Generate newsletter drafts | State-changing |
| Export | Produce Markdown/JSON artifacts | State-changing but no external publish |
| Audit | Explain provenance and decisions | Read-only |

No MCP tool should publish to beehiiv, email users, or send premium alerts without an explicit later approval design.

---

## Core Data Objects

### Candidate Summary

```json
{
  "candidate_id": "cand_...",
  "company_name": "Example GmbH",
  "legal_form": "GmbH",
  "court": "Charlottenburg (Berlin)",
  "case_number": "36e IN 123/26",
  "publication_date": "2026-06-15",
  "publication_type": "eroeffnung",
  "status": "review_ready",
  "source_count": 1,
  "evidence_count": 3,
  "score": null,
  "score_status": "unscored",
  "risk_flags": [],
  "updated_at": "2026-06-15T12:00:00Z"
}
```

### Evidence Item

```json
{
  "evidence_id": "ev_...",
  "source_provider": "official_insolvency_portal",
  "source_url": "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf",
  "retrieved_at": "2026-06-15T12:00:00Z",
  "field": "company_name",
  "value": "Example GmbH",
  "confidence": "high",
  "snippet": "Example GmbH | Charlottenburg (Berlin) | ...",
  "content_hash": "sha256:..."
}
```

### Tool Result Envelope

All tools should return a consistent envelope:

```json
{
  "ok": true,
  "data": {},
  "warnings": [],
  "errors": [],
  "audit_id": "audit_..."
}
```

For failures:

```json
{
  "ok": false,
  "data": null,
  "warnings": [],
  "errors": [
    {
      "code": "SOURCE_TIMEOUT",
      "message": "Official portal request timed out",
      "retryable": true
    }
  ],
  "audit_id": "audit_..."
}
```

---

## MCP Tool Backlog

Only the eight tools listed in **MCP v0: Keep It Tiny** are required for the first implementation. The remaining tools below are intentionally documented so they are not forgotten, but they should stay out of v0 unless a v0 workflow cannot work without them.

### 1. `radar_health`

Read-only health and readiness check.

**Input**

```json
{}
```

**Output**

```json
{
  "status": "ok",
  "database": {
    "connected": true,
    "path": "data/radar.duckdb"
  },
  "counts": {
    "candidates": 63,
    "review_ready": 12,
    "publish_ready": 3
  },
  "last_successful_source_run": "2026-06-15T08:00:00Z",
  "stale_sources": []
}
```

### 2. `radar_list_sources`

List configured source providers.

**Input**

```json
{
  "enabled_only": false
}
```

**Output**

```json
{
  "sources": [
    {
      "source_id": "official_insolvency_berlin",
      "name": "Official Insolvency Portal Berlin",
      "type": "official_jsf",
      "enabled": true,
      "trust_level": "A",
      "last_run_status": "success",
      "last_run_at": "2026-06-15T08:00:00Z"
    }
  ]
}
```

### 3. `radar_list_source_runs`

Inspect source-run history.

**Input**

```json
{
  "source_id": "official_insolvency_berlin",
  "status": null,
  "limit": 20
}
```

**Output**

```json
{
  "runs": [
    {
      "source_run_id": "run_...",
      "source_id": "official_insolvency_berlin",
      "status": "success",
      "started_at": "2026-06-15T08:00:00Z",
      "completed_at": "2026-06-15T08:00:14Z",
      "raw_records": 12,
      "new_candidates": 4,
      "duplicates": 8,
      "errors": []
    }
  ]
}
```

### 4. `radar_import_legacy_scout`

Read legacy `insolvency-scout` DuckDB records without mutating the legacy DB.

**Input**

```json
{
  "legacy_db_path": "/Users/ghassan/my-projects/insolvency-scout/data/insolvency_scout.duckdb",
  "since": "2026-06-01",
  "until": "2026-06-15",
  "dry_run": true
}
```

**Output**

```json
{
  "dry_run": true,
  "raw_records_seen": 311,
  "distinct_candidates": 63,
  "would_import": 63,
  "duplicates": 248,
  "warnings": [
    "Legacy scores imported as archived reference only"
  ]
}
```

### 5. `radar_run_acquisition`

Run a source acquisition job in the new system.

**Input**

```json
{
  "source_id": "official_insolvency_berlin",
  "date_from": "2026-06-15",
  "date_to": "2026-06-15",
  "dry_run": false
}
```

**Output**

```json
{
  "source_run_id": "run_...",
  "raw_records": 12,
  "new_candidates": 4,
  "duplicates": 8,
  "rejected": 0,
  "status": "success"
}
```

### 6. `radar_list_candidates`

Search and filter normalized candidates.

**Input**

```json
{
  "status": ["review_ready", "publish_ready"],
  "publication_date_from": "2026-06-01",
  "publication_date_to": "2026-06-15",
  "court": "Charlottenburg (Berlin)",
  "legal_forms": ["GmbH", "UG", "AG"],
  "min_score": null,
  "risk_flags": [],
  "query": null,
  "limit": 25,
  "offset": 0
}
```

**Output**

```json
{
  "candidates": [],
  "total": 0,
  "limit": 25,
  "offset": 0
}
```

### 7. `radar_get_candidate`

Return full candidate detail with evidence, enrichment, score, and review state.

**Input**

```json
{
  "candidate_id": "cand_...",
  "include_raw": false,
  "include_evidence": true
}
```

**Output**

```json
{
  "candidate": {},
  "evidence": [],
  "enrichments": [],
  "scores": [],
  "review_events": []
}
```

### 8. `radar_find_duplicates`

Find likely duplicate candidates.

**Input**

```json
{
  "candidate_id": null,
  "since": "2026-06-01",
  "threshold": 0.85,
  "limit": 50
}
```

**Output**

```json
{
  "groups": [
    {
      "canonical_candidate_id": "cand_...",
      "duplicates": ["cand_..."],
      "match_reason": "same_company_same_publication_date",
      "confidence": 0.98
    }
  ]
}
```

### 9. `radar_review_candidate`

Human/agent review action for candidate workflow state, score approval, and review notes. This is intentionally broad in v0 so agents have one simple write tool for candidate review.

**Input**

```json
{
  "candidate_id": "cand_...",
  "decision": "approve",
  "status": "publish_ready",
  "reviewer": "openclaw",
  "note": "Corporate filing verified from official portal",
  "score": {
    "company_value": 3,
    "asset_quality": 2,
    "sector_attractiveness": 4,
    "speed_of_action": 4,
    "legal_risk": 2
  }
}
```

Allowed decisions:

```text
approve
reject
needs_more_info
mark_duplicate
archive
```

Allowed statuses:

```text
raw_candidate
deduped_candidate
needs_review
review_ready
publish_ready
rejected
archived
```

**Output**

```json
{
  "candidate_id": "cand_...",
  "status": "publish_ready",
  "decision": "approve",
  "score_id": "score_...",
  "computed_score": 2.65,
  "audit_id": "audit_..."
}
```

### 10. `radar_enrich_candidate`

Run enrichment for one candidate.

**Input**

```json
{
  "candidate_id": "cand_...",
  "sources": ["openregister", "company_website", "github"],
  "force_refresh": false
}
```

**Output**

```json
{
  "candidate_id": "cand_...",
  "enrichment_run_id": "enr_...",
  "evidence_added": 4,
  "fields_updated": ["website_url", "industry", "employee_count"],
  "warnings": []
}
```

### 11. `radar_add_manual_evidence`

Add reviewed evidence from manual research.

**Input**

```json
{
  "candidate_id": "cand_...",
  "source_provider": "manual_research",
  "source_url": "https://example.com",
  "field": "revenue_estimate",
  "value": "3-5M EUR",
  "confidence": "medium",
  "snippet": "Annual report shows...",
  "reviewer": "ghassan"
}
```

### 12. `radar_propose_score`

Let the system propose score dimensions from evidence.

**Input**

```json
{
  "candidate_id": "cand_...",
  "scoring_version": "v1",
  "include_llm_rationale": true
}
```

**Output**

```json
{
  "candidate_id": "cand_...",
  "proposal": {
    "company_value": 3,
    "asset_quality": 2,
    "sector_attractiveness": 4,
    "speed_of_action": 4,
    "legal_risk": 2,
    "computed_score": 2.65,
    "category": "solid",
    "rationale": {
      "company_value": "Medium confidence; revenue not verified"
    }
  },
  "requires_approval": true
}
```

### 13. `radar_approve_score` (v1)

Approve or override a proposed score. This is the score that can appear in output.

For v0, prefer `radar_review_candidate` instead. Keep this as a later, more explicit tool when scoring workflows need finer control.

**Input**

```json
{
  "candidate_id": "cand_...",
  "company_value": 3,
  "asset_quality": 2,
  "sector_attractiveness": 4,
  "speed_of_action": 4,
  "legal_risk": 2,
  "reviewer": "ghassan",
  "rationale": {
    "company_value": "No verified revenue; moderate company footprint"
  }
}
```

**Output**

```json
{
  "score_id": "score_...",
  "computed_score": 2.65,
  "category": "solid",
  "status": "approved"
}
```

### 14. `radar_generate_candidate_brief`

Generate an evidence-grounded candidate brief.

**Input**

```json
{
  "candidate_id": "cand_...",
  "audience": "mna_investor",
  "max_words": 250
}
```

**Output**

```json
{
  "brief": {
    "thesis": "...",
    "why_it_matters": "...",
    "key_risk": "...",
    "action_step": "...",
    "confidence": "medium",
    "unsupported_claims": []
  }
}
```

### 15. `radar_review_candidate_for_publication`

Run compliance/editorial checks before issue inclusion.

**Input**

```json
{
  "candidate_id": "cand_...",
  "tier": "free"
}
```

**Output**

```json
{
  "publishable": false,
  "blocking_issues": [
    {
      "code": "MISSING_SOURCE",
      "message": "No durable evidence for employee-count claim"
    }
  ],
  "warnings": [
    {
      "code": "ADMIN_CONTACT_FREE_TIER",
      "message": "Administrator contact should not appear in free issue"
    }
  ]
}
```

### 16. `radar_create_issue_draft`

Create a newsletter issue draft from approved candidates.

**Input**

```json
{
  "issue_date": "2026-06-16",
  "tier": "free",
  "candidate_ids": ["cand_1", "cand_2", "cand_3"],
  "title": null,
  "include_disclaimer": true
}
```

**Output**

```json
{
  "issue_id": "issue_...",
  "status": "draft",
  "candidate_count": 3,
  "markdown_preview": "...",
  "warnings": []
}
```

### 17. `radar_get_issue_draft`

Retrieve a draft issue.

**Input**

```json
{
  "issue_id": "issue_...",
  "format": "markdown"
}
```

**Output**

```json
{
  "issue_id": "issue_...",
  "format": "markdown",
  "content": "...",
  "status": "draft"
}
```

### 18. `radar_export_issue`

Export a draft artifact. This does **not** publish externally.

**Input**

```json
{
  "issue_id": "issue_...",
  "format": "markdown",
  "destination": "data/exports"
}
```

**Output**

```json
{
  "path": "data/exports/issue-2026-06-16-free.md",
  "sha256": "..."
}
```

### 19. `radar_audit_trail`

Explain what happened to an object.

**Input**

```json
{
  "object_type": "candidate",
  "object_id": "cand_..."
}
```

**Output**

```json
{
  "events": [
    {
      "at": "2026-06-15T08:00:00Z",
      "actor": "system",
      "action": "candidate_created",
      "source_run_id": "run_..."
    }
  ]
}
```

---

## Optional MCP Tools

These are useful later but not required for the first implementation.

| Tool | Purpose |
|---|---|
| `radar_compare_sources` | Compare official scraper vs Insolvenz-Radar/InsolvenzIndex coverage |
| `radar_get_market_snapshot` | Return weekly counts by sector, court, legal form |
| `radar_list_reviews_needed` | Queue of candidates needing human decision |
| `radar_update_source_config` | Enable/disable sources or change non-secret config |
| `radar_run_vendor_bakeoff` | Structured two-week source quality comparison |
| `radar_create_alert_preview` | Draft premium alert without sending it |
| `radar_mark_export_ready` | Human approval gate before external copy/paste/publish |

---

## Safety Rules

1. All state-changing tools must write an audit event.
2. Tools must distinguish `dry_run=true` from actual writes.
3. LLM-generated content is never evidence.
4. Published candidates require at least one evidence item from trust level A or B.
5. Consumer/personal insolvency records must be rejected or quarantined.
6. Administrator contact details should be suppressed from free-tier outputs until legal review.
7. MCP tools must not send external emails, beehiiv publishes, Telegram alerts, or paid alerts in Phase 1.
8. OpenClaw can trigger a run, but the repo database is the source of truth.

---

## Recommended First MCP Milestone

Implement the minimal MCP server with:

```text
radar_health
radar_import_legacy_scout
radar_list_candidates
radar_get_candidate
radar_review_candidate
radar_create_issue_draft
radar_export_issue
radar_audit_trail
```

This gives OpenClaw enough surface area to operate the product without direct DB access, while delaying the fresh official scraper until the production core is solid.
