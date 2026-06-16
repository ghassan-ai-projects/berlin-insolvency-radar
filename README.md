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
- **Extracts** structured facts from raw notices via LLM (DeepSeek) with prompt hardening
- **Enriches** candidates with public-source data
- **Scores** opportunities deterministically across 5 weighted dimensions (1–5 scale)
- **Reviews** for legal, compliance, and evidence risks with self-correcting retry logic
- **Exports** ranked Markdown newsletter drafts with audit trails and disclaimers

## Quick Start

```bash
git clone https://github.com/ghassan-ai-projects/berlin-insolvency-radar.git
cd berlin-insolvency-radar
uv sync --extra dev
cp .env.example .env
# Edit .env with your DEEPSEEK_API_KEY (or set BI_RADAR_USE_MOCK_AGENTS=true for local dev)
```

Verify:

```bash
make check
```

Dry-run the pipeline:

```bash
uv run biradar phase2-check
```

Start the MCP server:

```bash
uv run biradar serve
```

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

Pre-release development. Phase 0 (foundation), Phase 1 (legacy import and editorial
workflow), and Phase 2 (autonomous agentic pipeline) are complete. 54 tests pass at
81% coverage. Live portal integration and production hardening are in progress.
