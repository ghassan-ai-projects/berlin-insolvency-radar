# Handoff: Berlin Insolvency Opportunity Radar

**Date:** 2026-06-15
**Purpose:** Complete project brief for a coding agent to build the newsletter pipeline.
**Status:** Research validated, pre-launch. Ready to build MCP v0 / Phase 0–1.

---

## 1. Overview

A curated weekly intelligence newsletter that scans German insolvency filings, ranks distressed company opportunities by value, and delivers actionable insights to B2B subscribers. Delivered via beehiiv.

**Tagline:** *Every week, I find and rank the most interesting insolvency opportunities in Berlin so you don't have to.*
**Motto:** The asset is the ranked intelligence, not the code.

## 2. Business Model

| Tier | Price | Content | Delivery |
|------|-------|---------|----------|
| **Free** | €0 | Top 3 opportunities + sector trends | Weekly email |
| **Paid** | €19/mo or €199/yr | Full ranked list (10–15), scoring breakdown, risk analysis | Weekly email + web archive |
| **Premium** | €49/mo or €499/yr | Everything in Paid + custom alerts by sector, real-time notification, priority support, API access | Real-time + weekly |

## 3. Target Audience & Pain Points

| Segment | Pain Point | What We Solve |
|---------|-----------|---------------|
| M&A Investors & PE | No off-market deal flow; high competition for healthy assets | Structured rankings of distressed corporate filings with normalized metrics |
| Creditors & Suppliers | **Double-payment liability** — paying the bankrupt entity instead of the liquidator means paying twice under German law | Early warning system when business partners file for insolvency |
| Turnaround Consultants | Fragmented court registries make prospecting inefficient | Centralized daily monitoring of Berlin court appointments and filings |
| M&A Brokers & Advisors | Need sell-side/buy-side mandates from distressed situations | Curated opportunity pipeline with scoring |
| Recruiters | High cost of sourcing premium talent | Alerts on major bankruptcies with employee scale |
| Corporate Founders | Hard to find roll-up or horizontal acquisition targets | Ranked acquisition opportunities |

## 4. Legal Guardrails (Non-Negotiable)

### Do
- ✅ Process ONLY corporate filings (GmbH, AG, UG, KG, OHG)
- ✅ Include prominent disclaimer: "Not investment or financial advice. For informational purposes only."
- ✅ Use permission-based subscription (opt-in, double opt-in)
- ✅ Attribute all data to source register links
- ✅ Present as business intelligence / financial journalism
- ✅ Take legal consultation before launch (~€300–500, German media/IT lawyer)

### Don't
- ❌ Consumer/personal insolvencies (GDPR red zone)
- ❌ Unsolicited marketing emails (UWG violation)
- ❌ Unsourced subjective claims (defamation risk)
- ❌ Store data beyond 6 months after proceedings conclude

## 5. Data Sources (Build Order)

### Phase 0–1: Manual (First 3 Issues)
- **Source:** insolvenzbekanntmachungen.de (manual browsing) + Insolvenz-Radar free tier
- **Cost:** €0
- **Why:** Validate concept before any automation

### Phase 2: Repo-Owned Autonomous Local Pipeline
- **Primary source:** fresh official-portal adapter for `neu.insolvenzbekanntmachungen.de`
- **Why:** canonical source, lower vendor dependency, better evidence provenance
- **Required standards:** source-run logging, saved evidence, parse errors, retries, idempotent dedupe
- **Output goal:** complete local issue artifacts ready for publication, but not published
- **Constraint:** no paid features and no paid data sources are required in this phase

### Phase 3+: Commercial Delivery, Publishing, And Paid Fallbacks
- **Publishing:** beehiiv workflow, archive delivery, launch/distribution operations
- **Discovery fallback:** Insolvenz-Radar or InsolvenzIndex if official coverage or reliability is not good enough
- **Enrichment:** OpenRegister, Unternehmensregister/Bundesanzeiger, Handelsregister, company website, GitHub where appropriate
- **Rule:** paid APIs can improve coverage and enrichment, but they should not replace the repo-owned product state

### Portal Technical Note
The German insolvency register has two databases:
- `alt.insolvenzbekanntmachungen.de` — proceedings initiated in or before 2017 (legacy format)
- `neu.insolvenzbekanntmachungen.de` — proceedings initiated in or after 2018 (dynamic interface)

Target **neu** exclusively for current opportunities.

## 6. Opportunity Scoring System (v1)

```
Opportunity Score = (A × 0.25) + (B × 0.20) + (C × 0.20) + (D × 0.20) − (E × 0.15)
```

| Letter | Dimension | Weight | Scoring (1–5) |
|--------|-----------|--------|---------------|
| A | Company Value | 25% | 1=Negligible → 5=€10M+ revenue, IP, brand |
| B | Asset Quality | 20% | 1=No assets → 5=Real estate, equipment, contracts |
| C | Sector Attractiveness | 20% | 1=Crisis → 5=High-growth, consolidation potential |
| D | Speed of Action | 20% | 1=Too late → 5=Early stage, time to negotiate |
| E | Legal/Risk Uncertainty | −15% | 1=Clean → 5=Complex disputes, litigation |

**Classification:**
- ≥ 3.0 → 🔥 Hot (Prioritize)
- 2.5–2.9 → ✅ Solid (Worth a look)
- 2.0–2.4 → 👀 Interesting (Monitor)
- < 2.0 → ⏸️ Low Priority (Skip)

## 7. Newsletter Issue Format

### Subject Line
```
Berlin Insolvency Radar — Week [W] [Date]: [Hook/Teaser]
```

### Structure per Issue
1. **Opening** (2–3 sentences): Market context, weekly trend
2. **Top 3 Opportunities** (free tier):
   - Company name (anonymized if needed)
   - Sector
   - Opportunity Score
   - Why It Matters (1–2 sentences)
   - Estimated Opportunity (€ range)
   - Key Risk (1 sentence)
   - Stage of proceedings
   - Action step (e.g. "Contact administrator by June 30")
3. **Sector Watch** (1 paragraph): Which sector is heating up
4. **Quick Notes**: Court decisions, regulatory changes
5. **Closing**: CTA to subscribe for full list

### Paid Version Adds
- Full ranked list (10–15)
- Scoring breakdown per company
- Contact / administrator info where available
- Detailed risk analysis for top 3

### Posting Cadence
- Weekly, send before **Tuesday 10:00 CET** (best B2B open rates)
- LinkedIn teaser post on Monday

## 8. Platform: beehiiv (Phase 3)

Chosen over Substack and Ghost:
- ✅ Custom cookie consent banner for EU GDPR compliance
- ✅ Mandatory double opt-in with 48h Smart Nudge
- ✅ 0% revenue cut (vs Substack's 10%)
- ❌ No native discovery (Substack is better) — compensate with own LinkedIn distribution

**Setup tasks for later publish phase:**
- Create beehiiv account
- Configure cookie consent banner
- Set up double opt-in
- Design free landing page with signup
- Create paid tier (€19/mo, €199/yr)

## 9. Launch Phases

### Phase 0: Foundation (Week 1–2)
- [ ] Legal consultation with German media/IT lawyer
- [ ] Standard disclaimers drafted
- [ ] Newsletter name + brand positioning decided
- [ ] Scoring framework finalized
- [ ] Issue template created
- [ ] Export-ready issue package format defined
- [ ] External publishing remains disabled

### Phase 1: Validate (Weeks 2–6)
- [ ] 3 manual/export-ready issues produced weekly
- [ ] Data manually sourced from insolvenzbekanntmachungen.de + Insolvenz-Radar free tier
- [ ] Internal quality review of issue usefulness, evidence, and score confidence
- [ ] Target: output is publication-ready locally, even though nothing is published yet

### Phase 2: Autonomous Local Pipeline (Weeks 6–10) — Build After MCP v0
- [ ] Fresh official-portal scraper in this repo
- [ ] Source-run logging, retries, parse errors, idempotent dedupe
- [ ] Fully agentic extraction, enrichment, scoring, risk review, and draft assembly with no human review required
- [ ] Use only official and free/public sources in this phase
- [ ] Generate export-ready Markdown and structured artifacts locally
- [ ] Keep external publishing disabled

### Phase 3: Publish And Monetize (Months 3–6)
- [ ] beehiiv account set up
- [ ] beehiiv paid tier activated (€19/mo)
- [ ] Archive access for paid subscribers
- [ ] Premium tier: €49/mo, custom alerts
- [ ] Evaluate paid fallback/enrichment sources if free pipeline coverage is insufficient
- [ ] LinkedIn launch post and distribution outreach
- [ ] LinkedIn ads test (€100 budget)
- [ ] One-off deep dives (€99–299)

### Phase 4: Expand (Month 6+)
- [ ] Custom scraper for cost control
- [ ] Additional cities (Munich, Hamburg, Frankfurt)
- [ ] API access for institutional clients
- [ ] Evaluate Ghost for full compliance control

## 10. Key Metrics

| Metric | Target |
|--------|--------|
| Subscribers (Phase 1 end) | 100+ |
| Open rate | 40%+ |
| Paid subscribers (Month 3) | 20 |
| Monthly revenue (Month 3) | €380+ |
| Paid subscribers (Month 6) | 50 |
| Monthly revenue (Month 6) | €950+ |
| Breakeven | Month 4 (~€50/mo costs) |

## 11. Open-Source Boundary (Don't Ship Proprietary Bits)

| Keep Proprietary | Can Open-Source Later |
|-----------------|-----------------------|
| Ranking algorithms | Scraper helpers (basic utilities) |
| Enriched financial dataset | Scoring templates (spreadsheets) |
| Automated email alert logic | Data-cleaning scripts |
| Centralized opportunity database | — |

## 12. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Not enough quality opportunities weekly | Medium | High | Cover Berlin metro + surrounding Brandenburg |
| GDPR/compliance issue | Low | High | Skip consumer, legal consult, beehiiv DOI + consent |
| Low subscriber conversion | Medium | Medium | Iterate format, test pricing |
| beehiiv lacks Substack discovery | Medium | Low | LinkedIn + own distribution compensates |
| Competitor (AcquireEU etc.) | Low | Medium | Curation edge — they're raw data, we're insight |
| Insolvenz-Radar API price increase | Low | Medium | Build own scraper as backup |

---

## 13. Quick Start for Coding Agent

### Agentic Architecture Guidance

Use LangGraph from v0 for orchestration/checkpointing, and LangChain for structured extraction, tool use, and drafting. In the revised plan, Phase 2 should be a **fully agentic local workflow** for artifact generation, but it must still stop short of external publishing. The safe architecture is:

```
agents act end to end -> deterministic code verifies guardrails -> audit log persists
```

Keep these deterministic:
- Corporate-only compliance filter
- Scoring formula and thresholds
- Deduplication
- Data retention/deletion
- Export/publishing gates

Use agents for:
- Notice-text extraction into structured fields
- Enrichment research with cited evidence
- Opportunity thesis drafting
- Unsupported-claim and compliance review
- Newsletter draft generation

See `strategy/agentic-implementation-plan.md` for the expanded implementation plan.
See `strategy/application-architecture.md` for the target application architecture and engineering standards.
See `strategy/testing-and-coding-standards.md` for the required test strategy, coding standards, review checklist, and CI gates.
See `strategy/phase-acceptance-tests.md` for Phase 0/1 acceptance tests and the definition of done.
See `strategy/data-source-strategy.md` for the source acquisition strategy.
See `strategy/mcp-interface.md` for the MCP-first tool contract.

### Existing Scraper / Pipeline

There is already a separate implementation at:

`/Users/ghassan/my-projects/insolvency-scout`

Use it as a reference implementation and legacy data source, not as code to copy into this repo. Local inspection on 2026-06-15 found:
- Scraper for `neu.insolvenzbekanntmachungen.de` in `src/insolvency_scout/sources/insolvenzbekanntmachungen.py`
- DuckDB database at `data/insolvency_scout.duckdb`
- MCP server in `src/insolvency_scout/server.py`
- Daily runner in `scripts/run-pipeline.sh`
- OpenClaw launchd service is running, but user `crontab` is empty
- OpenClaw internal cron currently has only a disabled `insolvency-scout-progress` job matching this project
- Latest observed DB scrape: `2026-06-10T08:00:04`
- DB state: 311 filings, 260 scores, 63 distinct company/date pairs

Critical caveat: the existing scraper feed has duplicates and weak run logging. The new repo should own the production implementation. Treat the legacy DuckDB as production data owned by the old project: open it read-only, never migrate it, never use it as this repo's working database, and clone it to a timestamped snapshot if experimentation is needed. Then disable old jobs so only one production pipeline runs.

### Immediate Build Tasks (MCP v0 / Phase 0–1)
1. **MCP server skeleton** — expose only v0 tools first: `radar_health`, `radar_import_legacy_scout`, `radar_list_candidates`, `radar_get_candidate`, `radar_review_candidate`, `radar_create_issue_draft`, `radar_export_issue`, `radar_audit_trail`.
2. **Scoring engine** — implement `opportunity_score(company_value, asset_quality, sector_attractiveness, speed_of_action, legal_risk)` with the weighted formula above. Configurable weights for future tuning.
3. **Data source module** — abstracted interface. Start with a new repo-owned DuckDB storage model, manual JSON/CSV input, and a read-only `insolvency-scout` DuckDB import adapter. Prep for a fresh official-portal scraper in this repo; Insolvenz-Radar remains a secondary source.
4. **Issue generator** — take scored companies, format into newsletter template (markdown). Output ready for local review or later paste into beehiiv.
5. **Data enrichment helpers** — parse insolvenzbekanntmachungen.de notice text, extract entity name, sector, proceed-to-date using free/public sources first.
6. **Filter module** — strip consumer insolvencies, keep only corporate filings.

### v0 Definition Of Done
- `radar_health` returns database status, candidate counts, stale-source warnings, and a clear next action for OpenClaw.
- `radar_import_legacy_scout` supports dry-run and real import without mutating the legacy DuckDB.
- Repo-owned DuckDB at `data/radar.duckdb` stores candidates, evidence, scores, reviews, issues, and audit events.
- Legacy DB imports prove the source file size, modified time, and content hash are unchanged.
- LangGraph coordinates the review/draft workflow with deterministic nodes for filter, dedupe, scoring, audit, and export.
- Candidate lists are deduplicated and default to records needing review.
- `radar_review_candidate` writes status, optional approved score, reviewer note, and audit event in one call.
- Issue draft/export creates local Markdown only; no beehiiv publishing or external email send.
- Consumer/personal records are rejected or quarantined before candidate review.
- Tests cover scoring, corporate filter, dedupe, legacy import, draft export, and audit writes.

### Where to Find Everything
All files in `/Users/ghassan/my-projects/berlin-insolvency-radar/`:
- `STRATEGY.md` — One-page strategy summary
- `README.md` — Full project overview
- `research/market.md` — Competitor analysis, trends
- `research/legal.md` — GDPR, compliance rules
- `research/data-sources.md` — API evaluations, portal split
- `research/business-model.md` — Pricing, creditor pain point
- `strategy/execution-plan.md` — Full launch plan
- `strategy/scoring-model.md` — Scoring framework
- `strategy/newsletter-template.md` — Issue format
- `strategy/application-architecture.md` — Application architecture, DuckDB schema, LangGraph workflows, and quality standards
- `strategy/testing-and-coding-standards.md` — Test strategy, coding standards, review checklist, and CI gates
- `strategy/phase-acceptance-tests.md` — Phase 0/1 acceptance tests and definition of done
- `strategy/data-source-strategy.md` — Source acquisition, enrichment, migration, and vendor strategy
- `strategy/mcp-interface.md` — MCP tool contract for OpenClaw/agent interaction
- **This file** `HANDOFF-TO-CODING-AGENT.md` — Everything in one place
