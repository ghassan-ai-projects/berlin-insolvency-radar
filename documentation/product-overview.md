# Product Overview

Berlin Insolvency Radar (BIRADAR) is an AI-powered system that monitors Berlin insolvency
filings, extracts structured intelligence, scores opportunities, and produces a ranked
weekly newsletter for investors and professionals.

## What It Does

1. **Scrapes** the official Berlin insolvency portal daily using JSF session management
2. **Extracts** structured facts from raw notices using LLM (DeepSeek) with XML-delimited prompts
3. **Enriches** candidates with public-source data and flags unsupported claims
4. **Scores** each opportunity deterministically across 5 weighted dimensions (1–5 scale)
5. **Reviews** for legal, compliance, and evidence risks — with self-correcting retry logic
6. **Exports** ranked Markdown newsletter drafts with audit trails and disclaimers

## Who It's For

- **Investors** looking for distressed asset opportunities in Berlin
- **Insolvency professionals** monitoring the market
- **Researchers** analyzing insolvency patterns
- **Developers** building on top of the MCP API

## What It Is Not

- Not a legal advice platform
- Not a consumer debt tracker (consumer insolvencies are filtered out)
- Not a real-time alert system (currently batch-oriented)
- Not a general-purpose web scraper

## Key Design Principles

- **Deterministic where possible:** Domain logic (compliance, deduplication, scoring) is pure functions with no LLM dependency
- **Fail-closed:** Errors quarantine candidates rather than passing them through
- **Audit everything:** Every mutation logs an immutable audit event with actor, action, and data
- **MCP-first:** All functionality is exposed through typed MCP tools with Pydantic-validated inputs
- **DuckDB-owned state:** Application state is owned by DuckDB, not in-memory graph checkpoints

## Business Model

Three tiers planned:

| Tier | Price | Content |
|------|-------|---------|
| Free | €0/mo | Top 3 opportunities, sector watch, disclaimer |
| Paid | €19/mo | Full ranked list, detailed evidence, admin contact |
| Premium | €49/mo | API access, historical data, priority support |
