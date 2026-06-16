# Security Policy

## Supported Release Line

Security fixes are currently targeted at the latest pre-release state only.

## Reporting A Vulnerability

Please do not open public issues for suspected vulnerabilities.

Report privately to the maintainers with:

- a clear description of the issue
- affected version or commit
- reproduction steps if available
- impact assessment
- any proposed mitigation

Until a dedicated security contact channel is published, use a private maintainer contact path rather than public issue trackers.

## Security Expectations

Berlin Insolvency Radar uses:

- a third-party LLM API (DeepSeek) — ensure your API key is stored in `.env` (gitignored)
- MCP over stdio (local-only by default)
- DuckDB for local data storage — restrict filesystem access to the data directory

When deploying on shared infrastructure, place the application behind a reverse proxy,
terminate TLS, and restrict access at the network layer. The MCP server has no built-in
authentication — it is designed for local/trusted use.

## Known Security Considerations

- **Prompt injection:** Scraped insolvency notices are passed to the LLM. The extraction
  and risk review agents use XML delimiters and prompt hardening to mitigate this vector.
- **Path traversal:** All file path construction uses `Path.resolve()` with bounds checks.
- **SQL injection:** All database queries use DuckDB parameterized queries (`?` placeholders).
- **Information disclosure:** MCP error responses use generic messages; details are logged
  server-side only.
