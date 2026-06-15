# Berlin Insolvency Opportunity Radar

**Status:** Research validated; MCP-first Phase 0 ready
**Last Updated:** 2026-06-15

## Concept

A curated weekly intelligence newsletter that scans German insolvency filings, identifies the highest-value distressed company opportunities in Berlin (and broader Germany), ranks them by opportunity score, and delivers actionable insights to buyers, investors, and advisors.

**Tagline:** *Every week, I find and rank the most interesting insolvency opportunities in Berlin so you don't have to.*

**Motto:** The asset is the ranked intelligence, not the code.

## Why This Exists

German corporate insolvencies hit a 10-year high in 2025 (24,064 cases, +10.3% YoY) and continue rising in 2026 (Q1: 6,275 filings, +6.5% YoY). Weak economy, high energy costs, skilled labor shortage, and international competition are driving sustained distress — especially in transport, hospitality, construction sectors.

Yet there's no curated, Berlin/Germany-focused weekly opportunity newsletter. Existing tools are either too broad (AcquireEU — 16 countries, €99/mo) or too raw (Insolvenz-Radar — unfiltered data feed). The gap is real.

## Business Model

| Tier | Price | What's Included |
|------|-------|-----------------|
| **Free** | €0 | Top 3 opportunities, brief |
| **Paid** | €19–29/mo | Full ranked list, scoring, deeper analysis |
| **Premium** | €49–99/mo | Custom alerts, real-time, API access |

## Audience

| Segment | Core Pain Point | Radar Solution | Business Outcome |
|---------|----------------|----------------|------------------|
| M&A Investors & PE | High competition for healthy assets; lack of distressed deal flow | Structured rankings of corporate filings with normalized asset metrics | Off-market asset acquisition at distressed valuations |
| Creditors & Suppliers | Financial loss from partner bankruptcies; **double-payment liability to liquidators under German law** | Early warning system alerting users when business partners file for insolvency | Avoidance of double payments; timely filing of creditor claims |
| Turnaround Consultants | Highly fragmented court registries make prospecting inefficient | Centralized, daily monitoring of Berlin court appointments and filings | Immediate pitching of restructuring services to liquidators |
| M&A Brokers & Advisors | Need sell-side/buy-side mandates from distressed situations | Curated opportunity pipeline with scoring | New billable mandates |
| Recruiters | High cost of sourcing premium talent in competitive industries | Alerts on major bankruptcies detailing affected employees and company scale | Rapid recruitment of displaced, highly skilled talent pools |
| Corporate Founders/Acquirers | Programmatic roll-up or horizontal acquisition targets hard to find | Ranked acquisition opportunities | Market share capture at distressed prices |

## Key Decisions (Research Phase)

### Legal
- Skip consumer insolvencies entirely — removes GDPR risk, keeps focus on acquisition opportunities
- Company-level data (GmbH, AG) is generally permissible for business intelligence
- One consulting session with a German media lawyer recommended before launch
- Disclaimers: not financial/legal advice

### Platform
- **Start on beehiiv** (not Substack) — better GDPR compliance (custom cookie consent, double opt-in with 48h Smart Nudge, 0% revenue cut vs Substack's 10%). Ghost if we need full control, but adds overhead.
- beehiiv's mandatory DOI + custom consent scripts significantly reduce legal risk in the EU market.
- Substack's rigidity on compliance makes it a legal liability for a B2B product in the European market.

### Launch Strategy
- Write 3 manual issues first to prove concept + scoring system
- Build only the smallest MCP-first production core before deeper automation
- Launch free, add paid tier after building audience

### Technical
- v0 is MCP-first: DuckDB-backed local database, LangGraph workflow, read-only legacy import, manual input, review, scoring, draft/export
- Do not run the old `insolvency-scout` pipeline and the new pipeline at the same time
- Build the fresh official scraper only after the v0 MCP core is stable
- Use Insolvenz-Radar/InsolvenzIndex as validation or fallback, not the default engine
- Scoring dimensions: company value, asset quality, sector attractiveness, speed of action, legal risk

### Open-Source Boundary (Phase 4+)
| Keep Proprietary | Open-Source Later |
|-----------------|-------------------|
| Ranking algorithms | Scraper helpers (basic court announcement utilities) |
| Enriched financial dataset | Scoring templates (spreadsheet-based evaluation sheets) |
| Automated email alert logic | Data-cleaning utilities (entity string extraction) |
| Centralized opportunity database | |

## Project Files

| File | Purpose |
|------|---------|
| `README.md` | This file — project overview |
| `HANDOFF-TO-CODING-AGENT.md` | **Complete build brief — start here** |
| `research/market.md` | Market research, competitor analysis, trends |
| `research/legal.md` | Legal & regulatory considerations |
| `research/data-sources.md` | Data sources & API evaluation |
| `research/business-model.md` | Pricing, monetization, audience analysis |
| `strategy/execution-plan.md` | Step-by-step launch plan |
| `strategy/scoring-model.md` | Opportunity scoring framework |
| `strategy/newsletter-template.md` | Issue format and structure |
| `strategy/application-architecture.md` | Best-in-class application architecture and engineering standards |
| `strategy/testing-and-coding-standards.md` | Test strategy, coding standards, review checklist, and CI gates |
| `strategy/phase-acceptance-tests.md` | Phase 0/1 acceptance tests and definition of done |
| `strategy/agentic-implementation-plan.md` | Critical LangGraph/LangChain implementation plan |
| `strategy/data-source-strategy.md` | Production data-source and acquisition strategy |
| `strategy/mcp-interface.md` | MCP-first tool contract for agent interaction |

## Sources

- Web research (2026-06-15)
- Destatis insolvency statistics (June 2026)
- Competitor site analysis (AcquireEU, Insolvenz-Radar, DailyDAC)
- External validation PDF provided by Ghassan (2026-06-15) — cross-referenced and incorporated

## Navigation

- All research materials in `research/`
- All strategy documents in `strategy/`
