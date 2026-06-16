# MCP API

Berlin Insolvency Radar exposes its functionality through an MCP server with 10 tools.
All tools use Pydantic-validated inputs and return `ResultEnvelope[T]` responses.

## Result Envelope

Every tool returns:

```json
{
  "ok": true,
  "data": { ... },
  "errors": [],
  "warnings": [],
  "audit_id": "audit_abc123",
  "next_action": "Call radar_export_issue to save this draft to disk."
}
```

- `ok` — whether the operation succeeded
- `data` — typed payload (tool-specific)
- `errors` — list of `{code, message, retryable}` objects
- `warnings` — non-fatal issues
- `audit_id` — reference to the audit event for this operation
- `next_action` — suggested next tool to call

## Tool Catalog

### `radar_health`
Check application health, database status, and next recommended action.

**Input:** *(none)*

**Output data:**
- `status` — "ok"
- `database.connected` — true/false
- `counts` — candidates by status
- `last_successful_source_run` — timestamp or null
- `next_action` — suggested workflow step

---

### `radar_import_legacy_scout`
Import or dry-run import from legacy Insolvenz-Scout DuckDB.

**Input:**
- `legacy_db_path` (string, required) — path to legacy DuckDB file
- `since` (string, optional) — YYYY-MM-DD filter
- `until` (string, optional) — YYYY-MM-DD filter
- `dry_run` (boolean, default: true)
- `actor` (string, default: "system")

**Output (dry_run=true):**
- `dry_run` — true
- `raw_records_seen` — total records found
- `distinct_candidates` — deduplicated count
- `rejected` — filtered out (consumer, non-corporate)
- `duplicates` — near-duplicate count

**Output (dry_run=false):**
- `dry_run` — false
- `distinct_candidates` — imported count
- `audit_id` — audit event reference

---

### `radar_list_candidates`
List candidates, defaulting to those needing work.

**Input:**
- `statuses` (array, optional) — filter by status
- `limit` (integer, default: 25, max: 100)
- `offset` (integer, default: 0)

**Output data:** Array of candidates, each with `candidate_id`, `status`, `evidence_count`, `score_status`, `next_action`.

---

### `radar_get_candidate`
Get full candidate detail with evidence, scores, reviews, and audit lineage.

**Input:**
- `candidate_id` (string, required)

**Output data:**
- `candidate` — full candidate record
- `evidence` — list of evidence snippets
- `source_lineage` — raw record provenance
- `latest_score` — most recent approved score
- `audit_events` — full audit history for this candidate

---

### `radar_review_candidate`
Review a candidate: approve, reject, needs_more_info, mark_duplicate, or archive.

**Input:**
- `candidate_id` (string, required)
- `decision` (string, required) — "approve" | "reject" | "needs_more_info" | "mark_duplicate" | "archive"
- `reviewer` (string, required)
- `note` (string, optional)
- `score_input` (object, optional) — 5-dimension scoring proposal (1–5 each)

**Output data:**
- `status` — new candidate status
- `score_id` — if score was approved
- `audit_id` — audit event reference

---

### `radar_create_issue_draft`
Create a newsletter issue draft from approved candidates.

**Input:**
- `week` (string, required) — format: YYYY-W## (e.g., "2026-W25")
- `tier` (string, required) — "free" | "paid"
- `candidate_ids` (array, required)
- `title` (string, required)
- `include_disclaimer` (boolean, default: true)
- `actor` (string, default: "system")

**Output data:**
- `issue_id` — new issue identifier
- `status` — "draft"
- `candidate_count` — number of valid candidates included
- `markdown_preview` — first 500 characters of the draft

---

### `radar_export_issue`
Export an issue draft to a local Markdown file.

**Input:**
- `issue_id` (string, required)
- `format` (string, default: "markdown")
- `actor` (string, default: "system")

**Output data:**
- `path` — absolute path to the exported file
- `sha256` — content hash for integrity verification

---

### `radar_audit_trail`
Retrieve audit events for an entity.

**Input:**
- `entity_type` (string, optional)
- `entity_id` (string, optional)
- `actor` (string, optional)
- `limit` (integer, default: 50, max: 200)

**Output data:** Array of audit events with `event_id`, `actor`, `action`, `entity_type`, `entity_id`, `request_data`, `result_data`, `timestamp`.

---

### `radar_list_source_runs`
Inspect source-run history for official acquisition runs.

**Input:**
- `source_id` (string, optional)
- `status` (string, optional)
- `limit` (integer, default: 20, max: 200)

**Output data:** Array of source runs with `source_run_id`, `source_id`, `status`, `records_seen`, `records_imported`, `started_at`, `completed_at`.

---

### `radar_run_workflow`
Trigger the production workflow pipeline from ingestion to local export.

**Input:**
- `start_date` (string, required) — YYYY-MM-DD
- `end_date` (string, required) — YYYY-MM-DD
- `dry_run` (boolean, default: false)

**Output data:**
- `status` — "success" | "failed"
- `current_step` — final step reached
- `export_path` — path to the exported Markdown file
- `issue_id` — issue identifier (if persisted)
- `warnings` — non-fatal issues encountered
- `errors` — fatal errors if status is "failed"

## Error Codes

| Code | Meaning | Retryable |
|------|---------|-----------|
| `VALIDATION_ERROR` | Invalid tool arguments | No |
| `TOOL_NOT_FOUND` | Unknown tool name | No |
| `CANDIDATE_NOT_FOUND` | Candidate ID does not exist | No |
| `ISSUE_NOT_FOUND` | Issue ID does not exist | No |
| `INVALID_TIER` | Tier not "free" or "paid" | No |
| `INVALID_DECISION` | Decision not in allowed set | No |
| `INVALID_STATUS` | Operation invalid for current status | No |
| `UNSUPPORTED_FORMAT` | Export format not supported | No |
| `NO_VALID_CANDIDATES` | No publish-ready candidates for draft | No |
| `WORKFLOW_FAILED` | Pipeline execution failed | Yes |
| `INTERNAL_ERROR` | Unhandled internal error | Yes |
