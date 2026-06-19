# Operational Upgrade Delivery

**Date:** 2026-06-19  
**Scope:** parser hardening, model decoupling, generic enrichment, new live sources, and operational validation

## What Was Completed

### 1. Live operation was split into explicit modes

- `full_live`
- `portal_only`
- `portal_with_stubs`

This removes the old ambiguity where one broken stage made the entire runtime look equally broken.

### 2. The portal parser was hardened

- HTML table responses are still supported
- JSF partial responses are still supported
- span/div-based live layouts are now supported
- known portal error pages are classified explicitly:
  - `too_many_results`
  - `search_form_returned_without_results`
  - `parser_mismatch`

This is materially better than the previous parser because it now distinguishes parser drift from portal behavior.

### 3. The LLM path is no longer tightly coupled to DeepSeek

- provider-neutral env vars were added:
  - `BIRADAR_LLM_API_KEY`
  - `BIRADAR_LLM_MODEL`
  - `BIRADAR_LLM_BASE_URL`
  - `BIRADAR_LLM_PROVIDER`
  - `BIRADAR_LLM_TIMEOUT_SECONDS`
- backward-compatible `DEEPSEEK_*` fallback remains supported
- extraction and risk review now depend on a shared runtime builder instead of constructing the provider directly

Result: switching providers is now a runtime/config choice, not a code edit.

### 4. Enrichment is now registry-based

- sources are registered once and resolved dynamically
- `config/sources.yaml` now controls per-source enablement
- new sources can be added as one lookup function plus one registry entry

This is the structural change needed to make source expansion cheap.

### 5. New enrichment sources were added

- `north_data`
- `wikidata`

These supplement the existing sources with better public company identity and sector signals.

### 6. Enrichment claims are now persisted as first-class records

- a dedicated `enrichment_claims` table was added
- pipeline persistence now stores normalized source claims, not only merged summary fields
- candidate detail retrieval now exposes:
  - `enrichment_summary`
  - `enrichment_claims`

This closes an important contract gap: source-specific enrichment evidence now survives beyond a single workflow run.

### 7. Enrichment source architecture is now modular

- `biradar.sources.enrichment` is now a package, not a single monolith
- runtime/client concerns live in dedicated modules
- the orchestrator is separate from the source adapters
- each source now has its own adapter module

This reduces the cost of adding or replacing sources and makes the source layer easier to reason about and test.

## Live Validation

### Confirmed working with real data

- official portal live acquisition succeeded in stubbed-downstream mode
- final `live-smoke-portal` run completed successfully after the refactor and fetched 438 live records in about 3.174 seconds
- `lookup_north_data("Zalando SE")` returned a real registry number and sector
- `lookup_wikidata("Zalando SE")` returned a real website and sector

### Confirmed still weak

- the fully live pipeline still times out in the extraction/model stage

That means the system is now operational at the acquisition and enrichment layers, but not yet fully operational at the model-dependent stage.

## Why This Version Is Better Than The Previous One

The old shape was brittle in three places:

- parser logic was too layout-specific
- model runtime was provider-specific
- enrichment growth required editing a fixed orchestrator

The current shape is better because each of those is now a replaceable seam:

- parser strategies are classified and extensible
- model backend is runtime-configurable
- enrichment sources are registry-driven and config-toggleable

This is the first version that looks like a maintainable product core rather than a one-off prototype.

## Remaining Design Work

The next design areas to improve are:

1. Add bounded retry and circuit-breaker behavior for live extraction/review calls.
2. Add a small evaluation set for extraction quality, not only runtime correctness.
3. Strengthen workflow typing so state contracts are less `dict`-shaped.

## Commit Sequence

1. `32eadd9 feat: add live smoke modes and stage reporting`
2. `985255c refactor: classify official portal parsing`
3. `70fd64a refactor: decouple llm runtime from deepseek`
4. `148dd96 refactor: add registry-based enrichment sources`
5. `7877e78 feat: add north data and wikidata enrichment`

## Validation Snapshot

- `make check` passed on 2026-06-19 after the final delivery changes
- the final live portal smoke command passed
- the new North Data and Wikidata adapters returned real data
