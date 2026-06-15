# berlin-insolvency-radar
Weekly curated intelligence newsletter — Berlin insolvency opportunity radar. Research, strategy, scoring, and pipeline automation for distressed company acquisitions.

## Phase 0 Skeleton

Phase 0 provides the safe local foundation:

- typed configuration from `config/`
- DuckDB schema bootstrapping
- stable MCP result envelopes
- health and audit tools
- deterministic domain modules
- a minimal auditable LangGraph health workflow

Phase 0 intentionally does not enable live scraping, email sending, alerting, or external publishing.

## Setup

Use `uv` so the project runs with the declared Python 3.12+ environment:

```bash
uv sync --extra dev
```

## Verify Phase 0

Run the full Phase 0 gate:

```bash
uv run make phase0-check
```

`make check` is an alias for the same Phase 0 gate.

Useful narrower checks:

```bash
uv run make test
uv run make test-acceptance
uv run pyright src/biradar
```

## Local Startup

Validate config:

```bash
uv run biradar check
```

Initialize the local DuckDB database and list the MCP v0 tools:

```bash
uv run biradar mcp-info
```

Run the MCP server over stdio:

```bash
uv run biradar serve-mcp
```

The default database path is `data/radar.duckdb`. The legacy Insolvency Scout database is configured as read-only input and must not be used as the active radar database.
