# Handoff: Berlin Insolvency Opportunity Radar

**Date:** 2026-06-15
**Purpose:** Complete project brief for a coding agent to build the newsletter pipeline.
**Status:** Research validated, pre-launch. Ready to build Phase 0–1.

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

### Phase 2: Automated Pipeline
- **Source:** Insolvenz-Radar paid API (~€29–49/mo)
- **Features:** REST API, JSON, HTTP-Push for real-time alerts, up to 100 items/page
- **Data depth (paid):** Company name, filing date, court, full notice text, financial metrics, purpose, industry, administrator details

### Phase 3+: Custom Scraper (if scaling)
- **Target:** neu.insolvenzbekanntmachungen.de (2018+, modern interface)
- **Reference scrapers:**
  - `insolvenz-scraper` by savas-grossmann (neu portal)
  - `InsolvencyAnnouncementsGer` by NDelventhal/Gassen (alt portal, legacy)
- **Also consider:** InsolvenzIndex API, OpenRegister API for enrichment

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

## 8. Platform: beehiiv

Chosen over Substack and Ghost:
- ✅ Custom cookie consent banner for EU GDPR compliance
- ✅ Mandatory double opt-in with 48h Smart Nudge
- ✅ 0% revenue cut (vs Substack's 10%)
- ❌ No native discovery (Substack is better) — compensate with own LinkedIn distribution

**Setup tasks:**
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
- [ ] beehiiv account set up
- [ ] Scoring framework finalized
- [ ] Issue template created
- [ ] "Coming soon" landing page published

### Phase 1: Validate (Weeks 2–6)
- [ ] 3 manual issues published weekly
- [ ] Data manually sourced from insolvenzbekanntmachungen.de + Insolvenz-Radar free tier
- [ ] LinkedIn launch post: "I built a tool that scans Berlin insolvency cases and ranks acquisition opportunities. Comment 'Berlin' for the first issue."
- [ ] Direct DM 20–30 M&A professionals
- [ ] Target: 100+ subscribers, 40%+ open rate

### Phase 2: Automate (Weeks 6–10) — Build This Now
- [ ] Insolvenz-Radar paid API integration (~€29–49/mo)
- [ ] Pipeline: API → filter by corporate only → score → generate issue draft
- [ ] AI-assisted editing (not fully automated)
- [ ] beehiiv paid tier activated (€19/mo)
- [ ] Archive access for paid subscribers

### Phase 3: Grow (Months 3–6)
- [ ] Premium tier: €49/mo, custom alerts
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

### Immediate Build Tasks (Phase 0–1)
1. **Scoring engine** — implement `opportunity_score(company_value, asset_quality, sector_attractiveness, speed_of_action, legal_risk)` with the weighted formula above. Configurable weights for future tuning.
2. **Data source module** — abstracted interface. Start with manual entry (JSON/csv). Prep for Insolvenz-Radar API integration.
3. **Issue generator** — take scored companies, format into newsletter template (markdown). Output ready to paste into beehiiv.
4. **Data enrichment helpers** — parse insolvenzbekanntmachungen.de notice text, extract entity name, sector, proceed-to-date.
5. **Filter module** — strip consumer insolvencies, keep only corporate filings.

### Where to Find Everything
All files in `~/ai-projects/projects/berlin-insolvency-opportunity-radar/`:
- `STRATEGY.md` — One-page strategy summary
- `README.md` — Full project overview
- `research/market.md` — Competitor analysis, trends
- `research/legal.md` — GDPR, compliance rules
- `research/data-sources.md` — API evaluations, portal split
- `research/business-model.md` — Pricing, creditor pain point
- `strategy/execution-plan.md` — Full launch plan
- `strategy/scoring-model.md` — Scoring framework
- `strategy/newsletter-template.md` — Issue format
- **This file** `HANDOFF-TO-CODING-AGENT.md` — Everything in one place
