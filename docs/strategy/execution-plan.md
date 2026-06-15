# Execution Plan

**Date:** 2026-06-15
**Status:** Pre-launch — ready to start Phase 1

---

## Phase 0: Foundation (Week 1–2)

### Legal
- [ ] One consulting session with German media/IT lawyer (~€300–500)
- [ ] Set up standard disclaimers (not financial advice, sourced from public registers)
- [ ] Decide on newsletter name + brand positioning

### Content Model
- [ ] Define the scoring framework (see `scoring-model.md`)
- [ ] Write 3 sample manual issues to validate format
- [ ] Create issue template

### Technical Foundation
- [ ] Build MCP v0 only: health, legacy import, candidate list/detail, review, draft/export, audit
- [ ] Use LangGraph from v0 to coordinate import, review, scoring, and draft/export
- [ ] Use a repo-owned DuckDB database and read-only legacy DuckDB import
- [ ] Keep the old `insolvency-scout` jobs disabled; do not run parallel production pipelines

### Platform
- [ ] Set up **beehiiv** account (not Substack — better GDPR compliance, 0% revenue cut, smart double opt-in with 48h nudge)
- [ ] Configure custom cookie consent banner for EU compliance
- [ ] Set up double opt-in with 48h Smart Nudge
- [ ] Configure free tier only to start
- [ ] Write "coming soon" landing page with email signup

---

## Phase 1: Validate (Weeks 2–6)

### Content
- [ ] Publish 3 manual issues (weekly)
- [ ] Source data from insolvenzbekanntmachungen.de + Insolvenz-Radar free tier
- [ ] Refine scoring model after each issue

### Distribution
- [ ] Post on LinkedIn: "I built a tool that scans Berlin insolvency cases and ranks acquisition opportunities. Comment 'Berlin' for the first issue."
- [ ] Direct DM to 20–30 M&A professionals, consultants, PE contacts
- [ ] Post in relevant Berlin/Germany startup or business groups

### Metrics
- [ ] Track: subscribers, open rate, reply rate
- [ ] Target: 100+ subscribers, 40%+ open rate by end of Phase 1

### Go/No-Go Decision
- After 3 issues, if subscriber growth is real and replies indicate demand → proceed to Phase 2
- If <50 subscribers or <30% open rate → reconsider format, distribution, or pivot

---

## Phase 2: Automate (Weeks 6–10)

### Technical
- [ ] Build fresh official-portal scraper in this repo, after MCP v0 is stable
- [ ] Keep source-run logs, parse errors, retries, and idempotent dedupe
- [ ] Evaluate Insolvenz-Radar/InsolvenzIndex as fallback or enrichment, not the default first engine
- [ ] Use AI-assisted editing (not fully automated — human review)
- [ ] Set up beehiiv paid tier

### Product
- [ ] Launch paid tier (€19/mo, €199/yr)
- [ ] Free: top 3 opportunities
- [ ] Paid: full ranked list (10–15) + scoring + analysis
- [ ] Add archive access for paid subscribers

### Marketing
- [ ] Reach out to 3–5 relevant newsletters for cross-promotion
- [ ] LinkedIn post announcing paid tier launch
- [ ] Offer first month free for first 20 paid subscribers

---

## Phase 3: Grow (Months 3–6)

### Premium Tier
- [ ] Launch Premium: €49/mo, custom alerts by sector/criteria
- [ ] Add reviewed high-signal notifications for high-value opportunities after legal review
- [ ] Offer one-off company deep dives (€99–299 each)

### Distribution
- [ ] Evaluate LinkedIn ads (small test: €100 budget)
- [ ] Referral program (1 month free for every referral who subscribes)
- [ ] Guest article in a relevant industry blog/newsletter

### Metrics Targets
- [ ] 500 total subscribers
- [ ] 30–50 paid subscribers
- [ ] €570–1,450/mo MRR
- [ ] 90%+ delivery rate, 40%+ open rate

---

## Phase 4: Expand (Month 6+)

### Product
- [ ] Evaluate platform switch to Ghost (full compliance control) if needed at scale
- [ ] API access for institutional clients
- [ ] Expansion to other German cities (Munich, Hamburg, Frankfurt)

### Business
- [ ] Bespoke reporting for PE firms (custom pricing)
- [ ] Consider part-time contractor for research/scoring
- [ ] Evaluate if newsletter → standalone data business is viable

---

## Key Milestones

| Milestone | Target Date | Success Criteria |
|-----------|------------|-----------------|
| Legal consultation done | Week 2 | ✅ |
| First manual issue published | Week 2-3 | Published, shared |
| 100 subscribers | Week 6 | Organic + outreach |
| Paid tier launches | Week 8 | €19/mo active |
| 20 paid subscribers | Month 3 | €380/mo MRR |
| 50 paid subscribers | Month 6 | €950/mo MRR |
| Breakeven (costs covered) | Month 4 | €50/mo costs covered |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Not enough quality opportunities weekly | Medium | High | Cover broader Berlin metro + surrounding states |
| GDPR/compliance issue | Low | High | Skip consumer filings, legal consult, disclaimers, beehiiv (mandatory DOI + consent scripts) vs Substack (no compliance tools) |
| Low subscriber conversion | Medium | Medium | Iterate on format, try different pricing |
| Platform discovery (beehiiv < Substack) | Medium | Low | beehiiv lacks Substack's native discovery, but GDPR compliance gap is more important. Rely on LinkedIn + own distribution. |
| Competitor from AcquireEU or similar | Low | Medium | Maintain curation edge — they're raw data, we're insight |
| Insolvenz-Radar API unreliable/price increase | Low | Medium | Build own scraper as backup |
