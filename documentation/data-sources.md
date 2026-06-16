# Data Sources

## Official Insolvency Portal (Berlin)

**Source:** `neu.insolvenzbekanntmachungen.de`
**Trust Level:** A (authoritative)

The primary data source. Berlin insolvency filings are published here by German courts.

### Scraping Approach

The `OfficialPortalAdapter` uses JSF session management:
1. GET the search form → extract `jakarta.faces.ViewState` and CSRF tokens
2. POST the search with date range and Berlin court filter (`lsom_bundesland = "BE"`)
3. Parse the HTML results table into structured records
4. Handle anti-bot detection (Cloudflare 403) with graceful degradation

### Limitations

- The portal split between `neu.` and `alt.` domains causes gaps in coverage
- JSF partial updates (Ajax) can return empty responses that need CDATA extraction
- Rate limiting: realistic delays (1.5s) and exponential backoff on retries
- Anti-bot measures: Cloudflare challenges block scraping; detected by 403 + "cloudflare" in body

## Commercial Sources (Future)

| Source | Type | Coverage | Cost |
|--------|------|----------|------|
| Insolvenz-Radar | Paid API | Germany-wide | ~€50/mo |
| InsolvenzIndex | Freemium | Germany | Free tier available |
| OpenRegister | Free | Company registry basics | Free |

## Enrichment Sources

Multi-source enrichment is implemented in `src/biradar/sources/enrichment.py`.
Each source is contacted sequentially with error isolation — a single failure
does not abort the pipeline. Set `BI_RADAR_ENRICH_REAL=1` to activate.

| Source | Data | Status |
|--------|------|--------|
| Bundesanzeiger | Annual reports, balance sheets, revenue estimates | Integrated |
| GitHub API | Organisation lookup, repos, stars, languages | Integrated (no auth) |
| Company Website | Homepage title, meta description, tech stack signals | Integrated |
| Handelsregister.de | Company registration details (legal form, court, HRB) | Integrated (may be blocked by anti-bot on free tier) |
| Unternehmensregister.de | Annual financial statements | Not yet integrated |

## Source Quality Model

Sources are classified by trust level:

| Level | Description | Examples |
|-------|-------------|----------|
| A | Official, authoritative | Official insolvency portal, court records |
| B | Commercial, verified | Paid APIs with documented accuracy |
| C | Community, curated | Open data projects, research databases |
| D | Unverified public | Web scraping, news articles |
| E | AI-generated | LLM inferences without source evidence |

Only trust level A and B sources contribute evidence. Inferences from lower-trust sources
are explicitly marked and gated by the risk review agent.
