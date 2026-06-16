# Plan: Multi-Source Enrichment Integration

**Date:** 2026-06-16
**Source:** Port from legacy `insolvency-scout` project (`src/insolvency_scout/agents/enrich_agent.py`)
**Status:** ✅ Implemented

## Overview

Replaced the hardcoded enrichment stub in `phase2_workflow.py::enrichment_node` with a 4-source enrichment pipeline. See `src/biradar/sources/enrichment.py` for implementation.

## Gating

`BI_RADAR_ENRICH_REAL=1` — when unset, returns mock `{"sector": "Unknown"}` (backward compatible).

## Files changed

| File | Change |
|------|--------|
| `src/biradar/sources/enrichment.py` | **New** — 4 source lookups + orchestrator |
| `src/biradar/storage/db.py` | Added `enrichments` table (migration `003_enrichments`) |
| `src/biradar/storage/repository.py` | Added `EnrichmentRepository` |
| `src/biradar/graph/phase2_workflow.py` | `enrichment_node` calls `enrich_candidate()` |
| `config/sources.yaml` | Added `enrichment:` section |
| `tests/unit/test_enrichment.py` | **New** — 21 tests (mock mode, failure isolation, slug, DNS) |
