# Data Source Strategy

**Date:** 2026-06-15
**Status:** Production data acquisition strategy

---

## Executive Summary

The old `insolvency-scout` project proved that the official German insolvency portal can be queried and that useful Berlin filings can be collected. It also exposed the main risks: duplicate filings, incomplete run logging, fragile enrichment, and too little evidence provenance.

The new repo should start fresh with a source strategy built around four layers:

1. **Authoritative discovery** — find insolvency publications from official or near-official sources.
2. **Commercial fallback** — use paid APIs when speed, coverage, or legal/operational stability matters more than cost.
3. **Company enrichment** — enrich only after a corporate filing is verified and deduplicated.
4. **Editorial validation** — every published claim must trace to a source, confidence level, or explicit inference.

OpenClaw can trigger jobs and report status. It should not own source state, deduplication, or publication logic.

---

## What The Old Project Used

The previous project at `/Users/ghassan/my-projects/insolvency-scout` used these sources:

| Source | Role | Current Assessment |
|---|---|---|
| `neu.insolvenzbekanntmachungen.de` | Primary official filing discovery | Keep as primary reference, but reimplement cleanly in this repo |
| Startupdetector RSS | Startup/news signal | Keep as weak secondary signal, not canonical insolvency evidence |
| Bundesanzeiger | Financial/annual-report enrichment | Keep, but use structured evidence capture and expect session/JS friction |
| Handelsregister portal | Legal-form/register enrichment | Keep as verification source, not bulk API unless accessed through a compliant provider |
| Company website guessing | Website/status/tech signal | Keep as low-confidence enrichment only |
| GitHub API | Tech/IP/talent signal | Keep only for technology companies and mark as inferred signal |

Known old-system findings:
- DB: `/Users/ghassan/my-projects/insolvency-scout/data/insolvency_scout.duckdb`
- Latest observed scrape: `2026-06-10T08:00:04`
- Rows: 311 filings, 260 scores, 63 distinct company/date pairs
- Duplicate pressure is high; many company/date pairs appear repeatedly
- `scrape_log` was not populated by the Berlin runner
- OpenClaw currently has no active daily insolvency pipeline job matching this project; only disabled `insolvency-scout-progress`

Conclusion: treat the old DB as production data. Use it read-only for backfill and comparison. Do not copy the old scraper code or run both pipelines.

### Legacy Database Protection Policy

The existing database at `/Users/ghassan/my-projects/insolvency-scout/data/insolvency_scout.duckdb` is production data for the old system.

Rules:

- Never write to the legacy database from this repo.
- Never run migrations against the legacy database.
- Never use the legacy database as the default DuckDB path for this repo.
- Never run destructive cleanup commands against the legacy project.
- Never use the live legacy database in tests except through a read-only connection and only when explicitly marked as an optional local smoke test.
- The repo-owned database must be `data/radar.duckdb`.
- Any experimentation, fixture generation, or schema exploration must use a cloned copy under this repo's ignored data area or a temporary directory.

Recommended clone locations:

```text
data/legacy_snapshots/insolvency_scout_YYYYMMDD.duckdb
tests/fixtures/legacy_scout_sample.duckdb
```

Required implementation safeguards:

- Open the legacy DB with DuckDB read-only mode.
- The import service should reject `legacy_db_path` values that equal the repo-owned `data/radar.duckdb`.
- The repository layer should only write to the repo-owned DB connection.
- Acceptance tests should assert that importing from a legacy DB path does not change the legacy file size, modified time, or content hash.
- Any tool that creates a clone must write the clone to a new path and must not overwrite the source.

Operational rule:

If fresh data from the old system is needed, first create a timestamped clone/snapshot, then import from that clone or from the live DB opened read-only. The old system remains the owner of its own database until it is explicitly retired.

---

## Source Layers

### Layer 1: Authoritative Discovery

#### 1. Official Insolvency Portal

**URL:** https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf

**Use for:** canonical insolvency publication discovery.

**Why it matters:**
- The official portal states that German insolvency courts publish required announcements there.
- It exposes search fields for court, state, publication date, company/name, seat, case number, register entry, and publication type.
- The search-help page says corporate/non-consumer proceedings can generally be searched during the whole procedure, while pure consumer proceedings have stricter search limits after two weeks.
- Results are capped at 1,000 except certain day-specific searches.
- Direct links to search results are not allowed/possible because search-result sessions expire.

**Implementation strategy:**
- Build a fresh JSF-aware adapter in this repo.
- Query by exact date windows, not broad ranges.
- Start with Berlin courts and Berlin state filter.
- Use publication types separately: `Eröffnungen`, `Sicherungsmaßnahmen`, `Abweisungen mangels Masse`, `Entscheidungen im Verfahren`, `Sonstiges`.
- Capture raw HTML/result row evidence and parsed fields.
- Store `source_run_id`, request parameters, response hash, parse status, and parser version.
- Treat an empty day as a successful zero-result run only if the portal responded cleanly.

**Primary filters:**
- `bundesland=Berlin`
- `sitz=Berlin` where useful
- company search patterns by legal form: `*GmbH*`, `*UG*`, `*AG*`, `*GmbH & Co. KG*`, `*KG*`, `*OHG*`, `*SE*`, `*eG*`
- publication date `from == to` for daily capture

**Do not:**
- Bulk-scrape consumer/personal insolvencies.
- Store first names, birthdays, or private addresses unless legally reviewed and strictly necessary.
- Depend on search-result URLs as durable source links.

#### 2. Official Legacy Portal

**URL:** legacy/alt portal for older proceedings, referenced by the official split between older and newer procedures.

**Use for:** historical research only.

For this newsletter, current opportunities are the product. The new implementation should target current/new portal data first and ignore pre-2018/legacy proceedings unless a paying customer explicitly needs historical backfills.

---

### Layer 2: Commercial Discovery And Fallback

#### 1. Insolvenz-Radar

**URL:** https://insolvenz-radar.de/

**Use for:** API fallback, validation, and possibly enrichment.

**Why it matters:**
- Public site advertises API and HTTP-Push, daily current insolvency data, watchlists, and email/Slack notifications.
- API documentation exposes `GET /entries/search`, API-key authentication via `X-API-Key`, pagination, wildcard search, field selection, business/consumer filters, register fields, administrator object, company purpose, message text, industry, and company metrics.
- Pricing page lists Light, Standard, Business, and Expert tiers. As of 2026-06-15, Business is the first tier in their table that includes administrator data, company purpose, publication text, and industry search.

**Best use:**
- Evaluate after the fresh official scraper exists.
- Use as cross-check for coverage and as an enrichment shortcut when revenue/employees/industry/message fields justify the price.
- Use `business_insolvencies=true` and explicit `fields`.

**Caution:**
- The fields most useful for the newsletter, especially publication text, company purpose, industry, and metrics, appear tied to higher plans.
- Do not let this become the only canonical source unless commercial reliability beats the official scraper.

#### 2. InsolvenzIndex

**URL:** https://www.insolvenzindex.de/

**Use for:** commercial fallback and competitive benchmark.

**Why it matters:**
- Public API docs describe company objects with HRB, legal form, court, location, WZ/NACE code, founding date, share capital, employee count, proceedings, and cross-references.
- API methods include companies, publications, search, watch, and webhooks.
- Pricing page lists API access on Pro and Team tiers, with high daily call limits compared with Insolvenz-Radar.

**Best use:**
- Compare coverage, freshness, and API fields against Insolvenz-Radar.
- Use if WZ code, employee count, company object normalization, and webhooks are stronger than Insolvenz-Radar for the product.

**Caution:**
- Validate data provenance and terms before building dependency.
- Pricing/features may be commercial-marketing oriented; test with real records before choosing.

---

### Layer 3: Company Enrichment

#### 1. OpenRegister

**URL:** https://openregister.de/

**Use for:** company profile enrichment, not primary insolvency discovery.

**Why it matters:**
- OpenRegister says it unifies company data from official registries and offers a REST API.
- Its API page advertises company and registry data, ownership intelligence, financial analysis, advanced search, realtime registry-backed requests, official Handelsregister filings, SDKs, webhooks, and MCP/integration support.
- Pricing page includes limited free/basic API access and a Pro tier with credits.

**Best use:**
- Resolve canonical company identity from name/register.
- Fetch legal form, register court, register number, management, financial metrics, ownership, annual reports, and employee counts.
- Use for enrichment after the filing is confirmed corporate and deduped.

**Caution:**
- Budget API credits carefully.
- Store only fields needed for scoring/editorial claims.

#### 2. Unternehmensregister / Bundesanzeiger

**URLs:**
- https://www.unternehmensregister.de/
- https://www.bundesanzeiger.de/

**Use for:** official financial filings and annual-report evidence.

**Why it matters:**
- Unternehmensregister describes itself as the central platform for company data and provides access to register entries and submitted documents from commercial, cooperative, company, and partnership registers.
- Bundesanzeiger search can surface annual financial statements and legally relevant company announcements, but sessions and JavaScript make scraping fragile.

**Best use:**
- Manual or semi-automated evidence capture for top opportunities.
- Pull annual report existence, balance sheet, revenue signals, and recent financial years where available.

**Caution:**
- Avoid brittle scraping as the first implementation path.
- Prefer OpenRegister or other structured providers for scale.

#### 3. Handelsregister / Registerportal

**URL:** https://www.handelsregister.de/

**Use for:** verification of legal identity and register facts.

**Why it matters:**
- The register portal covers commercial, cooperative, partnership, civil-law partnership, and association registers for all German federal states.
- It includes register announcements and warns that structured information can be non-binding and may vary from printouts or be incomplete.

**Best use:**
- Confirm company name, register number, register court, legal form, and status.
- Use as an evidence source for ambiguous entities.

**Caution:**
- Do not build a large scraping dependency here without legal/terms review.
- Use structured commercial access where possible.

#### 4. Company Website

**Use for:** operating-status and business-description signal.

**Best use:**
- Verify whether the business still has a live domain.
- Extract title/meta description, product language, contact page, and obvious tech stack.
- Use archived snapshots later if necessary.

**Caution:**
- Website existence is weak evidence.
- Domain guessing can create false positives. Require confidence and evidence URL.

#### 5. GitHub

**Use for:** technology/IP/talent signal.

**Best use:**
- Search only when company appears to be software/tech.
- Capture organization match confidence, repo count, recent activity, dominant languages, and stars.

**Caution:**
- GitHub org name matching is noisy.
- Treat as inference, not fact, unless company website links to the org.

#### 6. Startupdetector / News RSS

**URL:** https://www.startupdetector.de/feed/

**Use for:** contextual signal and lead discovery.

**Best use:**
- Find startup closures, layoffs, funding context, or news-driven distress.
- Cross-reference against official insolvency filings before publishing.

**Caution:**
- Never publish insolvency status from news/RSS alone.

---

## Additional Sources To Consider

| Source | Role | Priority | Notes |
|---|---:|---:|---|
| Justiz auction / asset auction sites | Asset liquidation signal | Medium | Useful for equipment/real estate-heavy opportunities |
| EU e-Justice insolvency register search | Cross-border validation | Low | Useful later for expansion outside Germany |
| North Data / company databases | Ownership/financial context | Medium | Evaluate cost and terms |
| LinkedIn/company pages | Employee/talent signal | Low | High privacy/compliance sensitivity; use only aggregate public signals |
| Company press/news search | Context and editorial color | Medium | Must cite; do not treat as legal source |
| Bundesagentur / job ads archives | Operating status/talent signal | Low | More useful for live companies than insolvencies |
| DPMA register | Patent/trademark/IP signal | Medium | Useful for IP-heavy opportunities |

---

## Data Acquisition Strategy

### Phase A: Baseline And Migration

Goal: create clean state in this repo without running two pipelines.

Build:
- Read-only import from legacy `insolvency_scout.duckdb`.
- Deduped candidate table in the new DB.
- Source quality report comparing raw rows vs distinct company/date/case records.
- Manual source-run records for imported legacy data.

Exit criteria:
- Legacy data can be queried without mutating old DB.
- Duplicate company/date rows collapse in new system.
- Old OpenClaw jobs stay disabled.

### Phase B: Fresh Official Portal Capture

Goal: own the canonical source acquisition in this repo.

Build:
- `OfficialInsolvencyPortalSource`.
- Daily date-window scraper.
- Source-run records with request parameters, response hash, parser version, result count, error count, and duration.
- Idempotent upsert keyed by source, court, case number, register entry, company name, publication date, publication type, and row hash.
- Golden fixtures from saved official portal HTML.

Scheduling:
- Run once daily early morning.
- Backfill last 14 days on first run.
- Do not use OpenClaw internal cron as the only scheduler; use a repo-owned CLI/job. OpenClaw may trigger or observe it.

### Phase C: Enrichment After Deduplication

Goal: enrich only candidates that pass corporate filtering.

Enrichment order:
1. Register identity: OpenRegister or Handelsregister.
2. Financial signals: OpenRegister, Unternehmensregister, Bundesanzeiger.
3. Business description: company website, company purpose, industry/WZ.
4. Tech/IP/talent: GitHub, DPMA, website tech signals.
5. News context: Startupdetector, web/news search, manually reviewed.

Rule:
No enrichment result should overwrite source facts. Store enrichment as evidence records with source, retrieval time, field name, value, confidence, and raw snippet/hash.

### Phase D: Commercial API Evaluation

Goal: decide whether a paid insolvency API is worth it.

Run a two-week bakeoff:
- Official scraper vs Insolvenz-Radar vs InsolvenzIndex.
- Compare freshness, coverage, fields, duplicate rate, API stability, legal terms, cost, and missing high-value cases.
- Use a fixed Berlin/Brandenburg sample and a few high-value sectors.

Decision criteria:
- If official scraper is stable and complete enough, keep paid APIs as validation/enrichment only.
- If official scraper is fragile, buy the cheapest tier that gives publication text and business filters.
- If commercial APIs provide company metrics that materially improve scoring, consider paid tier even with official scraper.

---

## Source Quality Model

Every source should be scored before its data affects public output.

| Dimension | Meaning |
|---|---|
| Authority | Is this official, commercial aggregation, news, or inference? |
| Freshness | How current is the record? |
| Stability | Does the source have API/docs/rate limits, or is it fragile HTML? |
| Coverage | Does it cover all relevant Berlin/Germany corporate filings? |
| Granularity | Does it include case number, court, register, administrator, message text, metrics? |
| Legal Risk | Does it expose personal data or terms restrictions? |
| Cost | Free, fixed monthly, per-call, or enterprise |
| Evidence Quality | Can we cite or store a durable evidence artifact? |

Recommended trust levels:

| Trust Level | Examples | Can Drive Public Claim? |
|---|---|---|
| A | Official insolvency portal, official register document | Yes |
| B | Paid API sourced from official portal, OpenRegister official-backed data | Yes, with source label |
| C | Bundesanzeiger/Unternehmensregister extracted fields | Yes, if evidence captured |
| D | Company website, GitHub, news/RSS | Only as context/inference |
| E | LLM-derived inference | No, unless reviewed and labelled |

---

## Data Model Requirements

Minimum tables/entities:

- `source_providers`: provider name, type, base URL, trust level, terms status
- `source_runs`: provider, started/completed timestamps, params, status, counts, errors, response hash
- `raw_records`: raw source payload or snapshot pointer, parser version, content hash
- `filings`: normalized insolvency filing, court, case number, publication date, type, source references
- `companies`: normalized company identity, legal form, register court, register number
- `filing_company_links`: many-to-one/one-to-one links with confidence
- `evidence_items`: source, field, value, snippet/hash, confidence, retrieved_at
- `enrichments`: derived structured fields with evidence references
- `scores`: scoring version, dimensions, rationale, reviewer status
- `publication_candidates`: issue/week assignment, editorial status, export status

Non-negotiables:
- Never insert without `source_run_id`.
- Never score without a normalized `filing_id`.
- Never publish without at least one evidence item.
- Never let LLM output become evidence by itself.

---

## Recommended Initial Source Config

```yaml
sources:
  - id: official_insolvency_berlin
    name: Official Insolvency Portal Berlin
    type: official_jsf
    trust_level: A
    enabled: true
    schedule: daily
    params:
      base_url: "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf"
      bundesland: "Berlin"
      date_window_days: 1
      backfill_days_on_first_run: 14
      company_patterns:
        - "*GmbH*"
        - "*UG*"
        - "*AG*"
        - "*GmbH & Co. KG*"
        - "*KG*"
        - "*OHG*"
        - "*SE*"
        - "*eG*"
      publication_types:
        - "Eröffnungen"
        - "Sicherungsmaßnahmen"
        - "Abweisungen mangels Masse"
        - "Entscheidungen im Verfahren"

  - id: legacy_insolvency_scout
    name: Legacy Insolvency Scout DuckDB
    type: legacy_duckdb
    trust_level: C
    enabled: false
    mode: read_only
    path: "/Users/ghassan/my-projects/insolvency-scout/data/insolvency_scout.duckdb"

  - id: openregister
    name: OpenRegister
    type: enrichment_api
    trust_level: B
    enabled: false
    use_for:
      - company_identity
      - financial_metrics
      - ownership
      - register_documents

  - id: insolvency_radar
    name: Insolvenz-Radar
    type: commercial_insolvency_api
    trust_level: B
    enabled: false
    use_for:
      - coverage_bakeoff
      - fallback_ingestion
      - publication_text
      - metrics

  - id: startupdetector
    name: Startupdetector RSS
    type: rss_context
    trust_level: D
    enabled: false
    url: "https://www.startupdetector.de/feed/"
```

---

## Open Questions

1. Should the official scraper cover only Berlin courts, or Berlin + Brandenburg from day one?
2. Should commercial APIs be evaluated before or after the first manual newsletter issue?
3. Which fields are legally safe for the free issue versus paid issue: administrator contact, director names, exact address, full notice text?
4. Is OpenRegister budget acceptable for top-10 weekly enrichment, or should enrichment remain mostly manual at first?
5. At what point, if ever, should the DuckDB MVP move to Postgres for concurrent multi-user writes?

---

## Sources Consulted

- Official insolvency portal search page: https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf
- Official insolvency portal search help: https://neu.insolvenzbekanntmachungen.de/ap/info_suche.jsf
- Insolvenz-Radar homepage/API/pricing: https://insolvenz-radar.de/, https://insolvenz-radar.de/api/, https://insolvenz-radar.de/preise/
- InsolvenzIndex API/pricing: https://www.insolvenzindex.de/api-docs, https://www.insolvenzindex.de/preise
- OpenRegister homepage/API/pricing: https://openregister.de/en, https://openregister.de/en/api, https://openregister.de/en/pricing
- Handelsregister portal: https://www.handelsregister.de/rp_web/welcome.xhtml
- Unternehmensregister: https://www.unternehmensregister.de/de
- Old project files inspected locally: `/Users/ghassan/my-projects/insolvency-scout/config/sources.yml`, `src/insolvency_scout/sources/`, `src/insolvency_scout/agents/enrich_agent.py`
