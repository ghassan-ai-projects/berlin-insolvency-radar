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
| `BIRADAR_LLM_API_KEY` | For generic LLM usage | *(none)* | Provider-neutral API key for OpenAI-compatible backends |
| `BIRADAR_LLM_MODEL` | For generic LLM usage | *(none)* | Model name for the configured provider |
| `BIRADAR_LLM_BASE_URL` | No | *(none)* | Custom OpenAI-compatible base URL |
| `BIRADAR_LLM_PROVIDER` | No | `openai_compatible` | Provider label used for runtime reporting |
| `BIRADAR_LLM_TIMEOUT_SECONDS` | No | `30` | Shared timeout for extraction and risk review |
| `BIRADAR_LLM_MAX_RETRIES` | No | `1` | Bounded retry count for transient LLM failures |
| `BIRADAR_LLM_RETRY_BACKOFF_SECONDS` | No | `1.5` | Linear backoff multiplier between LLM retry attempts |
| `DEEPSEEK_API_KEY` | Backward-compatible fallback | *(none)* | Legacy DeepSeek API key |
| `DEEPSEEK_API_BASE` | No | `https://api.deepseek.com/v1` | Legacy DeepSeek API base URL |
| `DEEPSEEK_MODEL` | No | `deepseek-chat` | Legacy DeepSeek model name |

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

### Enrichment Configuration

`config/sources.yaml` also contains:

```yaml
enrichment:
  enabled: true
  timeout_seconds: 10
  delay_between_sources: 0.3
  sources:
    bundesanzeiger: true
    github: true
    website: true
    handelsregister: true
    north_data: true
    wikidata: true
```

- `enabled: true` — live enrichment is active
- `enabled: false` — enrichment is skipped without substituting fake data
- `sources.<name>: true|false` — enable or disable individual registered enrichment adapters without code changes

## Settings (Programmatic)

`Settings` (in `config/settings.py`) provides runtime configuration:

- `project_root` — resolves to the repository root (derived from `__file__`, not `os.getcwd()`)
- `data_dir` — `project_root / "data"` (gitignored, stores DuckDB and checkpoints)
- `scoring` — dict placeholder (scoring config is loaded from YAML via `AppConfig`)

`AppConfig` loads and validates both `scoring.yaml` and `sources.yaml` via Pydantic.
