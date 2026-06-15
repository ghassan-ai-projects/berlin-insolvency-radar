# Data Sources Evaluation

**Date:** 2026-06-15
**Status:** Research only — no integration yet

---

## Primary Source

### insolvenzbekanntmachungen.de
- **Type:** Official German insolvency register (free, public)
- **Coverage:** All German insolvency courts
- **Search:** Free for first 2 weeks post-publication; restricted search (by court, name) after
- **Data available:** Company name, court, case number, proceedings type, filing date
- **API:** No official API
- **Data retention:** Removed 6 months after proceedings conclude
- **Cost:** Free
- **Legal status:** Public, official, authoritative

**Verdict:** The gold standard for accuracy but requires scraping or manual browsing.

---

## Technical Note: neu. vs alt. Portal Split

The federal portal operates two separate databases:
- **alt.insolvenzbekanntmachungen.de** — Historical proceedings initiated in or before 2017 (static, legacy format)
- **neu.insolvenzbekanntmachungen.de** — Modern proceedings initiated in or after 2018 (dynamic interface)

Any scraper must handle both, or target neu exclusively for current opportunities.

### Existing Open-Source Scrapers
| Name | Author | Coverage | Notes |
|------|--------|----------|-------|
| **InsolvencyAnnouncementsGer** | NDelventhal / Gassen | Primarily alt (legacy) | Python library using pandas, requests, BeautifulSoup4. Developed for accounting research at Humboldt University of Berlin. |
| **insolvenz-scraper** | savas-grossmann | neu (modern) | Python scraper monitoring neu.insolvenzbekanntmachungen.de. Checks client lists against active filings. |

**Verdict:** Useful reference when building a custom scraper at scale phase. Not needed for proof-of-concept (use Insolvenz-Radar API or manual browsing).

---

## Third-Party API Providers

### Insolvenz-Radar
- **URL:** insolvenz-radar.de
- **API:** Yes — RESTful API with API key auth
- **Plans:** Free (limited) → ~€49/mo (Standard/Business/Expert)
- **Data depth:** Varies by plan — basic: company name, filing date, court. Paid: full notice text, financial metrics, purpose, industry
- **Features:** HTTP-Push for real-time alerts, CSV export
- **Cost:** Free tier sufficient for MVP (limited queries)

**Verdict:** Best option for the test phase. Free tier covers manual scanning + limited API. Upgrade later.

### InsolvenzIndex
- **URL:** insolvenzindex.de
- **API:** Yes — API key, filters, pagination, CSV/JSON export
- **Pricing:** Unknown (commercial)
- **Coverage:** German insolvency data

**Verdict:** Potential alternative or secondary source.

### OpenRegister
- **URL:** openregister.de
- **Focus:** Handelsregister + Bundesanzeiger company data (including insolvency)
- **API:** Yes
- **Pricing:** Freemium — paid for volume

**Verdict:** Useful for enrichment (company financials, ownership structure) rather than primary sourcing.

### Apify Scrapers
- Several open-source/pre-built scrapers for insolvenzbekanntmachungen.de
- **Cost:** Pay-per-use via Apify platform
- **Risk:** Scrapers may break when the register changes; reliability varies

**Verdict:** DIY option if API costs become prohibitive at scale.

---

## Recommendation by Phase

| Phase | Source | Why |
|-------|--------|-----|
| **Proof of concept** (first 3 issues) | Manual browsing of insolvenzbekanntmachungen.de + Insolvenz-Radar free tier | Zero cost, validates concept |
| **Pre-launch** | Insolvenz-Radar paid tier (~€29–49/mo) | Reliable API, structured data |
| **Scale** (100+ paid subscribers) | Custom scraper + enrichment from OpenRegister | Cost control, full control |
| **Maturity** | Custom scraper + multiple API sources | Best coverage, data quality |
