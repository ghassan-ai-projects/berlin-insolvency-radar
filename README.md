# Berlin Insolvency Radar

AI-powered insolvency intelligence for Berlin. Monitors official insolvency filings,
extracts structured facts, scores investment opportunities, and produces a ranked
weekly newsletter — all through a typed MCP API.

## Why BIRADAR

Berlin sees 60–180 actionable corporate insolvencies per year. Investors, turnaround
professionals, and analysts currently sift through raw court notices manually.
BIRADAR automates the pipeline: scrape, extract, enrich, score, review, and export
— with deterministic guardrails, full audit trails, and fail-closed safety.

## What It Does

- **Scrapes** the official Berlin insolvency portal with JSF session management
- **Extracts** structured facts from raw notices via a provider-neutral OpenAI-compatible LLM adapter
- **Enriches** candidates with registry-style public-source adapters
- **Scores** opportunities deterministically across 5 weighted dimensions (1–5 scale)
- **Reviews** for legal, compliance, and evidence risks with self-correcting retry logic
- **Exports** ranked Markdown newsletter drafts with audit trails and disclaimers

## Quick Start

```bash
git clone https://github.com/ghassan-ai-projects/berlin-insolvency-radar.git
cd berlin-insolvency-radar
uv sync --extra dev
cp .env.example .env
# Edit .env with your BIRADAR_LLM_API_KEY or DEEPSEEK_API_KEY
```

### Verify (code quality, no network)

```bash
make check          # format, lint, typecheck, unit + acceptance + e2e tests
```

No `.env` or API key needed — tests use fixtures and stubs exclusively.

---

## Production Mode

A production run scrapes the **live** official Berlin insolvency portal
(`neu.insolvenzbekanntmachungen.de`), calls a **live** OpenAI-compatible model
backend for fact extraction and risk review, hits **live** enrichment sources
(Bundesanzeiger, GitHub, company websites, North Data, Wikidata), and persists
everything to `data/radar.duckdb`.

### Prerequisites

```bash
cp .env.example .env
# Set BIRADAR_LLM_API_KEY=sk-... and BIRADAR_LLM_MODEL=... in .env
# Or keep using the backward-compatible DEEPSEEK_* variables
# Verify config/sources.yaml has official_insolvency_berlin.enabled: true
uv sync --extra dev
```

### Run the pipeline

```bash
# Scrape the last 7 days, extract, enrich, score, review, export
uv run biradar pipeline-run \
  --start-date 2026-06-09 \
  --end-date 2026-06-16
```

This connects to the **live portal** and the **live DeepSeek API**. It produces:

- `data/radar.duckdb` — persisted state with audit trail
- `data/exports/issue_draft_*.md` — ranked Markdown newsletter
- `data/exports/issue_data_*.json` — structured JSON package
- `data/checkpoints.sqlite` — LangGraph checkpoint for resume

### Run the MCP server

```bash
uv run biradar serve     # stdio MCP server with full tool catalog
```

---

## Development & CI (fixture-backed, no network)

These commands use **fixtures and stubs** — no `.env`, no API key, no network:

```bash
# Deterministic pipeline validation (fixture HTML + stub extractor/reviewer/enricher)
uv run biradar pipeline-check

# Individual test tiers
make test               # unit tests
make test-acceptance    # acceptance tests
make test-e2e           # e2e tests (non-live only)
```

`pipeline-check` runs the full workflow against a temporary DuckDB using fixture
data and deterministic stubs, then verifies database counts. It never touches
the live portal or any external API.

## Documentation

- [Product Overview](documentation/product-overview.md) — What it is, who it's for
- [Getting Started](documentation/getting-started.md) — Setup and first pipeline run
- [How It Works](documentation/how-it-works.md) — Pipeline flow and data lifecycle
- [Architecture](documentation/architecture.md) — 6-layer design and key decisions
- [MCP API](documentation/mcp-api.md) — Tool catalog and result envelope contract
- [Configuration](documentation/configuration.md) — YAML config and environment variables
- [Scoring Model](documentation/scoring-model.md) — Weighted 5-dimension formula
- [Data Sources](documentation/data-sources.md) — Official portal and enrichment sources
- [Legal & Compliance](documentation/legal-and-compliance.md) — GDPR, press law, corporate-only filtering
- [Testing Standards](documentation/testing-standards.md) — Test tiers and coverage targets
- [Security Model](documentation/security-model.md) — Threat model and hardening measures

## Open Source

- [License](LICENSE) — MIT
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Support](SUPPORT.md)

MIT was chosen because the core value is the data pipeline and intelligence output,
not the code. The project benefits from community contributions to scrapers, agents,
and export formats.

## Status

Pre-release development with a production-oriented local workflow. The repository
includes full local validation, a live portal path, and export-only workflow
execution without external publishing.
