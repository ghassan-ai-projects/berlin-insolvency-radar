# Getting Started

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A DeepSeek API key (for LLM extraction and risk review)

## Installation

```bash
git clone https://github.com/ghassan-ai-projects/berlin-insolvency-radar.git
cd berlin-insolvency-radar
uv sync --extra dev
```

## Configuration

```bash
cp .env.example .env
```

Edit `.env` with your DeepSeek API key:

```
DEEPSEEK_API_KEY=sk-your-key-here
```

For local development without API calls, enable mock mode:

```
BI_RADAR_USE_MOCK_AGENTS=true
```

## Verify Installation

```bash
make check
```

This runs format check, lint, typecheck, unit tests, and acceptance tests (54 tests total).

## Run The Pipeline

### Dry-run (no persistence, uses fixture data)

```bash
uv run biradar phase2-check
```

### Full pipeline with live portal scraping

```bash
uv run biradar run-phase2 --start-date 2026-06-10 --end-date 2026-06-16
```

### MCP Server

Start the MCP server for tool-based interaction:

```bash
uv run biradar serve
```

The MCP server exposes 10 tools over stdio. Connect any MCP-compatible client.

## Next Steps

- Read [How It Works](how-it-works.md) for the pipeline flow
- Read [MCP API](mcp-api.md) for the full tool catalog
- Read [Architecture](architecture.md) for the design decisions
