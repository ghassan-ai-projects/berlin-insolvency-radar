# Strategy: The Berlin Insolvency Opportunity Radar

This document captures the core strategy. Full details in `/research/` and `/strategy/`.

## Core Thesis

**The asset is ranked intelligence, not code.** The value lies in curation, scoring, and editorial insight — not the data pipeline. Existing competitors provide raw data (Insolvenz-Radar) or broad coverage (AcquireEU). No one curates Berlin-specific, ranked, actionable opportunities.

## Why Now

German corporate insolvencies are at a 10-year high and rising (24,064 in 2025, +10.3%; Q1 2026 +6.5%). Transport, hospitality, construction are the hardest-hit sectors. Strong tailwinds for distressed M&A through at least 2027.

## Business Model

- **Free:** Top 3 opportunities weekly (build audience, validate demand)
- **Paid (€19/mo):** Full ranked list + scoring + analysis
- **Premium (€49/mo):** Custom alerts, real-time notifications, API access

## Launch Strategy

1. **Legal first:** One session with German media lawyer (skip consumer filings → eliminates GDPR risk)
2. **3 manual issues on beehiiv:** Prove concept, refine scoring. beehiiv chosen over Substack for GDPR compliance (custom cookie consent, mandatory double opt-in, 0% revenue cut vs Substack's 10%).
3. **MCP-first v0 before automation:** DuckDB-backed local database, LangGraph workflow, read-only legacy import, manual input, review, scoring, draft/export.
4. **No parallel pipelines:** the old `insolvency-scout` project is a reference and backfill source, not a second production system.
5. **Fresh scraper after the core is stable:** build the official-portal adapter in this repo only after v0 is pleasant to use.
6. **Add paid tier at Month 2** when the format is proven.

## Brand Position

*Every week, I find and rank the most interesting insolvency opportunities in Berlin so you don't have to.*

## Key Files

| File | Purpose |
|------|---------|
| `README.md` | Full project overview |
| `research/market.md` | Market size, trends, competitor analysis |
| `research/legal.md` | GDPR, press law, compliance |
| `research/data-sources.md` | API evaluations, sourcing strategy |
| `research/business-model.md` | Pricing, unit economics, acquisition channels |
| `strategy/execution-plan.md` | Full phased launch plan |
| `strategy/scoring-model.md` | Opportunity scoring framework |
| `strategy/newsletter-template.md` | Issue format and structure |
| `strategy/application-architecture.md` | Best-in-class application architecture and engineering standards |
| `strategy/testing-and-coding-standards.md` | Test strategy, coding standards, review checklist, and CI gates |
| `strategy/phase-acceptance-tests.md` | Phase 0/1 acceptance tests and definition of done |
| `strategy/agentic-implementation-plan.md` | LangGraph/LangChain architecture and build plan |
| `strategy/data-source-strategy.md` | Source acquisition, enrichment, migration, and vendor strategy |
| `strategy/mcp-interface.md` | MCP-first tool contract for OpenClaw and agents |

## Current Status

**Phase 0: Foundation / MCP v0** — Legal + content model definition in progress; coding should start with the smallest MCP-first core.

Next action: Read `HANDOFF-TO-CODING-AGENT.md`, `strategy/application-architecture.md`, `strategy/testing-and-coding-standards.md`, and `strategy/phase-acceptance-tests.md`, then implement MCP v0. Legal consult and first issue remain required before public launch.
