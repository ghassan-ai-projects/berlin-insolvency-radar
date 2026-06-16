# Security Model

## Trust Assumptions

Berlin Insolvency Radar is designed for **local/trusted use**. The MCP server runs over
stdio with no built-in authentication. When deploying on shared infrastructure, place
the application behind a reverse proxy, terminate TLS, and restrict access at the network
layer.

## Threat Model

### External Threats

| Threat | Mitigation |
|--------|------------|
| Prompt injection via scraped notices | XML-delimited data injection with "treat as data" instructions |
| Path traversal in export paths | `Path.resolve()` bounds check + `week` regex validator |
| SQL injection | DuckDB parameterized queries (`?` placeholders) throughout |
| API key exposure | `.env` gitignored; env vars only; `.env.example` documents format |
| Anti-bot/scraping detection | JSF session management, realistic delays, graceful degradation |

### Internal Threats

| Threat | Mitigation |
|--------|------------|
| Rogue MCP tool calls | Local stdio only; document trust boundary |
| Checkpoint tampering | SQLite 0o600 permissions; WAL mode |
| Information disclosure in errors | Generic MCP error messages; details logged server-side |
| Legacy DB path traversal | `Path.resolve()` bounds check (planned) |
| Rate limiting / DoS | Singleton execution lock for Phase 2 workflow (planned) |

## Key Management

- `DEEPSEEK_API_KEY` is read from environment only
- `.env` is in `.gitignore` — never committed
- `.env.example` documents the format without actual keys
- `BI_RADAR_USE_MOCK_AGENTS=true` enables local development without API keys

## Data Storage

- All application data stored in DuckDB (`data/radar.duckdb`)
- Checkpoint state in SQLite (`data/checkpoints.sqlite`) with WAL mode and 0o600 permissions
- Export files written to `data/exports/`
- The `data/` directory is gitignored

## Deployment Hardening

When deploying beyond local use:

1. Place behind nginx/Caddy with TLS termination
2. Add API key authentication to the MCP transport layer
3. Restrict filesystem access to the `data/` and `exports/` directories
4. Run as a dedicated non-root user
5. Set up log rotation and monitoring
6. Configure firewall rules to allow only trusted IPs
7. Review the rate limiting and singleton lock for the Phase 2 workflow
