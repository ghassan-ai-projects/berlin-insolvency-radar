# How It Works

## Runtime Model

BIRADAR runs as a batch pipeline, executed on demand or on a schedule.

```
CLI → run_phase2_pipeline() → LangGraph Workflow → DuckDB + Export
        │                           │
        ▼                           ▼
  OfficialPortal            8-node state machine:
  (JSF scraping)            ingest → normalize → dedupe
                            → extraction → enrichment
                            → scoring → risk_review
                            → draft_assembly → export
```

## Pipeline Flow

### 1. Acquisition
The `OfficialPortalAdapter` manages a JSF session against the live insolvency portal:
- Fetches the search form, extracts `jakarta.faces.ViewState` and CSRF tokens
- Submits a date-range search with Berlin court filter
- Parses the HTML results table into structured records
- Handles anti-bot detection (Cloudflare 403) with graceful degradation

### 2. Ingestion & Normalization
Raw records enter the LangGraph workflow. The `ingest_node` initializes state,
then `normalize_and_compliance_node` applies the corporate-only filter:
- Checks `legal_form` against an allowlist (GmbH, UG, AG, etc.)
- Scans `raw_text` for consumer indicators ("Privatinsolvenz", "Verbraucherinsolvenz")
- Non-corporate filings are quarantined immediately

### 3. Deduplication
Deterministic hash-based dedup on (company_name, court, case_number).
Duplicates are marked and excluded from further processing.

### 4. Extraction
The LLM (DeepSeek) extracts structured facts from the raw notice text:
- Company name, legal form, court, case number, filing date
- Administrator, proceeding stage, sector hints
- Consumer likelihood flags
- Evidence snippets with confidence scores

Data is wrapped in `<raw_notice>` XML tags with explicit "treat as data" instructions
to prevent prompt injection.

### 5. Enrichment
Free/public sources are queried for additional context (sector, employees, etc.).
If an HTTP 403 or Cloudflare block is encountered, the candidate is marked
`blocked_by_anti_bot` and proceeds with lower confidence.

### 6. Scoring
Deterministic weighted formula across 5 dimensions (1–5 scale):
- Company value (25%), asset quality (20%), sector attractiveness (20%),
  speed of action (15%), legal risk (20%)
- Categories: Hot (≥3.0), Solid (2.5–2.9), Interesting (2.0–2.4), Low Priority (<2.0)
- Below-threshold candidates are auto-quarantined

### 7. Risk Review
The LLM reviews each candidate for compliance, legal, and evidence risks:
- Unsupported enrichment claims (non-inference, no source URL) trigger immediate quarantine
- Failed reviews retry up to 2 times, then auto-quarantine (fail-closed)
- Passing candidates are promoted to `publish_ready`

### 8. Draft Assembly & Export
Export-ready candidates are assembled into a newsletter draft with:
- Ranked opportunities with scores and evidence
- Audit summary (total records, candidates, quarantined, errors)
- Markdown formatted output with disclaimer
- JSON data package for programmatic consumption

## Data Lifecycle

```
Raw Record → Candidate → Extraction Result → Enrichment → Score → Review → Export
     │            │              │                │           │        │        │
     ▼            ▼              ▼                ▼           ▼        ▼        ▼
  raw_records  candidates   extraction_       enrichment_  scores  reviews  issues
                              results          results
```

All durable state is written to DuckDB via the repository layer. The LangGraph workflow
uses checkpointing (SQLite with WAL mode) for resumability across process restarts.

## Retry & Resilience

- **Scraping:** 3 retries with exponential backoff; anti-bot detection stops retries
- **Extraction:** Falls back to JSON regex parsing if structured output fails; returns safe mock on total failure
- **Scoring:** Deterministic validation rejects out-of-bounds LLM proposals
- **Risk Review:** 2 retries max; auto-quarantine on exhaustion (fail-closed)
- **Checkpointing:** SQLite-backed LangGraph saver with WAL mode and 0o600 permissions
