# Source Expansion Research

**Date:** 2026-06-19
**Goal:** Identify additional data sources for acquisition and enrichment, and define a source architecture that makes future integrations easy

## Executive Recommendation

Yes, there are better source options than relying almost entirely on the live insolvency JSF portal plus ad hoc enrichment scrapers.

The strongest next sources are:

1. **Unternehmensregister** as the best official secondary source
2. **Handelsregister** as the best official register-change source
3. **OpenCorporates API** as the easiest general-purpose normalization and provenance source
4. **BRIS / EU business register search** as a cross-border identity fallback

The most important architectural conclusion is this:

- do **not** keep adding sources as more functions inside one file
- move to a **registry + adapter + normalized claim** model before source count grows

## What Exists Today

The repo currently uses:

- `neu.insolvenzbekanntmachungen.de` as the primary acquisition source
- ad hoc enrichment from:
  - Bundesanzeiger
  - GitHub
  - company website
  - Handelsregister

That is workable, but too fragile and too centralized in one module.

## Best New Sources

### 1. Unternehmensregister

**Link:** https://www.unternehmensregister.de/de
**Type:** Official central company-data portal
**Best use:** Secondary acquisition, corroboration, enrichment, register documents

Why it matters:

- the official site describes itself as the central platform for company data
- it explicitly says users have access to register entries and documents from the commercial, cooperative, partnership, and civil-law-partnership registers
- it also explicitly lists **insolvency court announcements** among the accessible contents

Evidence:

- [Unternehmensregister homepage](https://www.unternehmensregister.de/de)
- [Unternehmensregister contents page](https://www.unternehmensregister.de/de/so-gehts/inhalt)

Why this is high value:

- it is an official source
- it can act as a second path when the insolvency portal is brittle
- it can add linked company context and register documents

Best role in BIRADAR:

- secondary acquisition source
- source of register context for companies already found in the insolvency portal
- fallback lookup by company name / EUID

Integration difficulty:

- medium
- likely session/search mechanics, but still much cleaner than inventing non-official sources

### 2. Handelsregister

**Link:** https://www.handelsregister.de/rp_web/welcome.xhtml
**Type:** Official common register portal of the German federal states
**Best use:** Company identity, register announcements, liquidation/status changes

Why it matters:

- the official portal states it provides the commercial register plus other registers and **register announcements**
- this is useful for validating legal form, court, company existence, and status changes around insolvent entities

Evidence:

- [Handelsregister portal](https://www.handelsregister.de/rp_web/welcome.xhtml)

Best role in BIRADAR:

- enrichment
- identity confirmation
- register-announcement monitoring
- better legal-form and court validation than website scraping

Integration difficulty:

- medium to high
- useful, but likely sensitive to session/search behavior

### 3. OpenCorporates API

**Link:** https://api.opencorporates.com/documentation/API-Reference
**Type:** Commercial/open API over company-register data
**Best use:** Normalization, company matching, provenance-rich enrichment

Why it matters:

- the official API docs say it exposes company information as JSON/XML
- it supports company search and company detail lookups
- it emphasizes provenance, source URLs, freshness, and confidence metadata

Evidence:

- [OpenCorporates API reference](https://api.opencorporates.com/documentation/API-Reference)

Best role in BIRADAR:

- company normalization
- identifier reconciliation
- cross-checking name, status, address, and source provenance
- fast enrichment layer without scraping each source directly

Integration difficulty:

- low
- easiest source on this list to add cleanly

Important limitation:

- it is not the authoritative insolvency source for Germany
- use it as enrichment and normalization, not as the primary filing source

### 4. BRIS / EU Business Register Search

**Link:** https://e-justice.europa.eu/topics/registers-business-insolvency-land/business-registers-search-company-eu_en
**Type:** Official EU business-register interconnection search
**Best use:** Cross-border company matching and identity fallback

Why it matters:

- the EU e-Justice portal says EU business registers have been interconnected and searchable since June 2017
- this is useful when a company has cross-border entities or when German register matching is ambiguous

Evidence:

- [EU business-register search page](https://e-justice.europa.eu/topics/registers-business-insolvency-land/business-registers-search-company-eu_en)

Best role in BIRADAR:

- fallback identity reconciliation
- cross-border parent/subsidiary context
- enrichment for non-purely domestic corporate structures

Integration difficulty:

- medium
- likely better as a targeted fallback source than a default enrichment pass

## Sources To Keep, But Reposition

### Insolvenzbekanntmachungen

**Link:** https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf
Keep it as the primary acquisition source, because it is still the authoritative live insolvency publication path.

But do not let it remain the only serious source.

### Bundesanzeiger

**Link:** https://www.bundesanzeiger.de/pub/en/start
Keep it as an enrichment/corroboration source for legally relevant company publications, not as the primary insolvency feed.

### Company Website

Keep it, but downgrade it conceptually:

- useful for weak signals
- not a trust anchor
- should not be treated as equivalent to official registers

### GitHub

Keep it only for a narrow segment:

- tech firms
- software-heavy targets
- product/engineering signal

It should be optional, not a core enrichment assumption.

## Source Strategy By Role

### Primary Acquisition

- `insolvenzbekanntmachungen_neu`
- later: `insolvenzbekanntmachungen_alt` for historical backfill if needed

### Secondary Acquisition / Corroboration

- `unternehmensregister`

### Official Enrichment

- `handelsregister`
- `bundesanzeiger`
- `unternehmensregister`

### Identity / Normalization

- `opencorporates`
- `bris_search`

### Weak-Signal Enrichment

- `company_website`
- `github`

## Recommended Source Ranking

If the goal is operational value with minimal integration pain:

1. Add **Unternehmensregister**
2. Add **OpenCorporates**
3. Refactor current enrichment into a modular registry
4. Revisit **Handelsregister** after the architecture is modular
5. Add **BRIS** only as a targeted fallback

## Architecture Recommendation

The repo should move to a source system like this:

```text
src/biradar/sources/
  acquisition/
    base.py
    insolvenzbekanntmachungen_neu.py
    unternehmensregister.py
  enrichment/
    base.py
    bundesanzeiger.py
    handelsregister.py
    opencorporates.py
    website.py
    github.py
    bris.py
  models.py
  registry.py
  orchestrator.py
```

### Core Interfaces

Acquisition:

```python
class AcquisitionSource(Protocol):
    source_name: str
    trust_level: str
    def fetch(self, query: AcquisitionQuery) -> FetchResult: ...
```

Enrichment:

```python
class EnrichmentSource(Protocol):
    source_name: str
    trust_level: str
    def lookup(self, company: CompanyRef) -> SourceResult: ...
```

Normalized output:

```python
class SourceClaim(BaseModel):
    field: str
    value: str
    source_name: str
    source_url: str | None
    confidence: float | None
    claim_type: Literal["observed", "derived", "inferred"]
```

### Why This Matters

This design makes a new source cheap to add:

1. implement one adapter
2. return normalized claims
3. register it
4. enable it in config

No giant `if source_name == ...` block. No one-file enrichment monster.

## Config Recommendation

`config/sources.yaml` should evolve from a single primary-source config into per-source entries like:

```yaml
sources:
  insolvency_portal_neu:
    role: acquisition
    enabled: true
    trust_level: A
    priority: 100

  unternehmensregister:
    role: acquisition_secondary
    enabled: true
    trust_level: A
    priority: 80

  handelsregister:
    role: enrichment
    enabled: true
    trust_level: A
    priority: 90

  opencorporates:
    role: enrichment
    enabled: true
    trust_level: B
    priority: 70
```

## Recommendation For The Next Build Step

If the goal is both better data and easier source expansion, the next implementation sequence should be:

1. refactor current source architecture into adapters + registry
2. add `Unternehmensregister` adapter
3. add `OpenCorporates` adapter
4. move current `Handelsregister` logic into the new adapter shape
5. only then add more sources

## Bottom Line

The best additional source is **Unternehmensregister**.

The easiest high-value source to add cleanly is **OpenCorporates**.

The most important engineering move is not adding five more scrapers. It is making the source layer modular first, so every future source is a small adapter instead of another round of entanglement.
