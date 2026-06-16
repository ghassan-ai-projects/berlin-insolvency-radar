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
- [ ] Define the export-ready issue artifact format and publishing handoff package
- [ ] Keep external publishing disabled until the autonomous local flow is stable
- [ ] Document what a future beehiiv handoff will require, but do not configure it yet

---

## Phase 1: Validate (Weeks 2–6)

### Content
- [ ] Prepare 3 manual/export-ready issues locally (weekly)
- [ ] Source data from insolvenzbekanntmachungen.de + Insolvenz-Radar free tier
- [ ] Refine scoring model after each issue

### Distribution
- [ ] Skip public launch and outbound distribution in this phase
- [ ] Review issue quality internally against the target audience use cases
- [ ] Decide whether the output is strong enough to justify future publishing work

### Metrics
- [ ] Track: issue quality, candidate coverage, duplicate rate, false-positive rate, and time-to-draft
- [ ] Target: 3 strong local issues with stable confidence and evidence quality by end of Phase 1

### Go/No-Go Decision
- After 3 issues, if the local output is strong and the workflow is stable → proceed to Phase 2
- If issue quality is weak or evidence is thin → improve scoring, sourcing, or draft structure before automation

---

## Phase 2: Autonomous Local Pipeline (Weeks 6–10)

### Technical
- [ ] Build fresh official-portal scraper in this repo, after MCP v0 is stable
- [ ] Keep source-run logs, parse errors, retries, and idempotent dedupe
- [ ] Add scheduled local runs with durable workflow state and restart safety
- [x] Add a fully agentic extraction, enrichment, scoring, risk-review, and draft-assembly workflow without requiring human review
- [ ] Use only official and free/public sources in this phase; no paid APIs, no paid datasets
- [ ] Keep deterministic compliance, quarantine, evidence, and export gates
- [ ] Export complete local issue artifacts: Markdown, structured JSON, and run/audit summary

### Product
- [ ] Produce a full ranked issue draft automatically from live acquisition
- [ ] Keep output local and reviewable; do not publish externally in this phase
- [ ] Generate "newsletter-ready" artifacts that could be pasted into a publishing tool later
- [ ] Include enough evidence and confidence metadata for each ranked company

### Operational Exit Criteria
- [ ] Repeated scheduled runs complete without manual intervention
- [ ] The system can go from fresh scrape to export-ready issue artifact through the full agent workflow
- [ ] Candidate quality is stable enough that quarantines and confidence thresholds catch weak records without human review
- [ ] No paid feature, paid archive, paid alert, or paid source is required for the pipeline to operate

---

## Phase 3: Publish And Commercialize (Months 3–6)

### Platform And Distribution
- [ ] Set up beehiiv publishing workflow
- [ ] Add archive delivery and operational publishing steps
- [ ] Reach out to 3–5 relevant newsletters for cross-promotion
- [ ] LinkedIn post announcing launch
- [ ] Evaluate LinkedIn ads (small test: €100 budget)

### Paid Product
- [ ] Launch paid tier (€19/mo, €199/yr)
- [ ] Free: top 3 opportunities
- [ ] Paid: full ranked list (10–15) + scoring + analysis
- [ ] Add archive access for paid subscribers
- [ ] Offer first month free for first 20 paid subscribers

### Premium And Commercial Data
- [ ] Launch Premium: €49/mo, custom alerts by sector/criteria
- [ ] Add reviewed high-signal notifications for high-value opportunities after legal review
- [ ] Offer one-off company deep dives (€99–299 each)
- [ ] Evaluate Insolvenz-Radar/InsolvenzIndex and other paid sources as fallback, validation, or enrichment only after the free pipeline is stable

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
| Autonomous local issue generation | Week 10 | Fresh scrape to export-ready issue runs unattended |
| Paid tier launches | Month 3 | €19/mo active |
| 20 paid subscribers | Month 4 | €380/mo MRR |
| 50 paid subscribers | Month 6 | €950/mo MRR |
| Breakeven (costs covered) | Month 5 | €50/mo costs covered |

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
