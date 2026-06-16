# Configuration

## Files

| File | Purpose |
|------|---------|
| `config/scoring.yaml` | Scoring weights and thresholds |
| `config/sources.yaml` | Source adapter modes and parameters |
| `.env` | Environment variables (gitignored) |
| `.env.example` | Documented environment variable template |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | For LLM features | *(none)* | DeepSeek API key |
| `DEEPSEEK_API_BASE` | No | `https://api.deepseek.com/v1` | DeepSeek API base URL |
| `DEEPSEEK_MODEL` | No | `deepseek-chat` | Model name for LLM calls |
| `BI_RADAR_USE_MOCK_AGENTS` | No | *(false)* | Set to `true`/`1` for mock LLM mode |

## Scoring Configuration (`config/scoring.yaml`)

```yaml
version: "1.0"
weights:
  company_value: 0.25
  asset_quality: 0.20
  sector_attractiveness: 0.20
  speed_of_action: 0.20
  legal_risk: 0.15
thresholds:
  hot: 3.0
  solid: 2.5
  interesting: 2.0
```

Weights must sum to 1.0 across all 5 dimensions. Thresholds define the category boundaries.

## Sources Configuration (`config/sources.yaml`)

```yaml
sources:
  official_insolvency_berlin:
    kind: insolvency_portal
    name: Official Insolvency Portal Berlin
    enabled: true
    trust_level: A
    mode: normal
    params:
      url: https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf
      court: BE
```

- `mode: normal` — live scraping
- `mode: fixture` — use fixture HTML for testing

## Settings (Programmatic)

`Settings` (in `config/settings.py`) provides runtime configuration:

- `project_root` — resolves to the repository root (derived from `__file__`, not `os.getcwd()`)
- `data_dir` — `project_root / "data"` (gitignored, stores DuckDB and checkpoints)
- `scoring` — dict placeholder (scoring config is loaded from YAML via `AppConfig`)

`AppConfig` loads and validates both `scoring.yaml` and `sources.yaml` via Pydantic.
