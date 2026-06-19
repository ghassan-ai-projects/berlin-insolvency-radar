# Parser, Model, And Enrichment Direction

**Date:** 2026-06-19
**Reviewer:** Codex
**Purpose:** Answer the concrete concerns about testing truth, parser design, model coupling, and enrichment extensibility

## First Correction

The repo has been tested locally, but not fully in the sense you meant.

What was actually tested in this review:

- full local non-live repo path
- fixture-backed pipeline path
- unit parser tests against repo fixtures
- unit enrichment tests against mocked source functions

What was not tested here:

- live portal against the current real HTML/JSF structure
- live DeepSeek extraction and review quality
- live enrichment against current third-party source behavior

So the honest statement is:

- local implementation: tested
- live product behavior: not yet validated in this review

## What I Re-tested Specifically

I ran these additional focused tests:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_official_portal.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_enrichment.py -v
```

They both passed.

That proves:

- the current parser works for the current fixture assumptions
- the enrichment orchestrator works for its current mocked source contract

That does not prove:

- the parser matches the current live portal DOM
- the enrichment approach will scale cleanly as more sources are added

## 1. Parser: Yes, There Is A Better Way

### Current Shape

The current parser is hard-coded around a table-oriented extraction path in [`src/biradar/sources/official_portal.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/sources/official_portal.py:371).

It assumes:

- HTML results are in a `table`
- rows are `tr`
- fields are fixed-position `td` cells

The tests reinforce that shape:

- [`tests/unit/test_official_portal.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/unit/test_official_portal.py:11)
- [`tests/fixtures/official_portal/sample_response.html`](/Users/ghassan/my-projects/berlin-insolvency-radar/tests/fixtures/official_portal/sample_response.html:1)

That is acceptable for a first adapter. It is weak for a government JSF portal that can change markup without changing semantics.

### Better Parser Strategy

The parser should be redesigned as a versioned adapter, not a single DOM assumption.

Recommended shape:

1. Split `fetch` from `parse`.
2. Store raw live responses as dated fixtures.
3. Implement parser strategies by response shape:
   - full HTML table layout
   - JSF partial-response layout
   - span/div result-card layout
   - known error pages like "too many hits" and form-returned-without-results
4. Normalize every strategy into one `RawPortalRecord` model.

### Better Technical Design

Instead of one `_parse_response()` doing everything, use something like:

```python
class PortalResponseParser(Protocol):
    def can_parse(self, payload: str) -> bool: ...
    def parse(self, payload: str) -> list[RawPortalRecord]: ...
```

Then register:

- `HtmlTableParser`
- `JsfPartialParser`
- `SpanListParser`
- `PortalErrorParser`

This improves:

- testability
- live-debugging
- fixture capture
- change isolation when the portal moves again

### Validation Standard For Parser

I would not trust this scraper until these tests exist:

1. One fixture from the current live portal for each known response shape.
2. A test for "too many results" producing a classified error, not silent zero records.
3. A test for "search form returned again" producing a classified failure.
4. A recorded live smoke run with exact dates and expected record count behavior.

## 2. DeepSeek Coupling: Yes, It Is Too Tight

### Current Shape

The code imports `ChatOpenAI` directly in both agent modules and reads DeepSeek-specific env vars inline:

- [`src/biradar/agents/extraction.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/extraction.py:35)
- [`src/biradar/agents/risk_review.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/agents/risk_review.py:46)

This is better than hardcoding only one model name, but it is still provider-coupled because:

- the provider client is constructed inside the business function
- the provider choice is hidden from the service/container layer
- prompt execution and provider transport are mixed together

### Better Model Abstraction

You want a provider-neutral interface for structured generation.

Recommended seam:

```python
class StructuredLLM(Protocol):
    def invoke_json(self, prompt: str) -> dict[str, Any]: ...
```

Then implement adapters like:

- `DeepSeekStructuredLLM`
- `OpenAIStructuredLLM`
- `AnthropicStructuredLLM`
- `LocalStructuredLLM`

The extraction and risk-review modules should depend on the protocol, not on `ChatOpenAI`.

### Better Ownership Boundary

Move model construction into DI:

- config chooses provider/model
- container builds provider adapter
- agents receive that adapter

That gives you:

- model switching without touching extraction logic
- easier testing
- clearer runtime configuration
- one place to add retries, JSON-mode enforcement, logging, and rate limits

### Minimal Refactor Direction

If you want the smallest useful change:

1. Add an `llm_provider` section to config.
2. Create `agents/llm.py` with a provider factory.
3. Replace direct `ChatOpenAI(...)` construction with `build_structured_llm(settings)`.
4. Keep the extraction/review prompt logic intact for now.

That alone would remove most of the bad coupling.

## 3. Enrichment: It Works, But It Is Not Generic Enough

### Current Shape

The current enrichment code is a single module with:

- HTTP helper functions
- per-source lookup functions
- source ordering
- aggregation rules
- source disabling behavior

See [`src/biradar/sources/enrichment.py`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/sources/enrichment.py:1).

The orchestration loop is this:

- fixed `source_defs` list in [`enrich_candidate()`](/Users/ghassan/my-projects/berlin-insolvency-radar/src/biradar/sources/enrichment.py:588)
- fixed `_aggregate_result()` logic in the same file

That is fine for 3 sources. It becomes brittle at 6 to 10 sources.

### Main Problems

1. New source addition requires editing one large file.
2. Source capabilities are implicit, not declared.
3. Aggregation logic is tied to source names like `"github"` and `"website"`.
4. There is no normalized claim model that separates raw source facts from merged candidate facts.

### Better Enrichment Design

Use a source-plugin pattern.

Recommended seam:

```python
class EnrichmentSource(Protocol):
    source_name: str
    def lookup(self, company_name: str) -> SourceResult: ...
```

And a normalized result model:

```python
class SourceClaim(BaseModel):
    field: str
    value: str
    confidence: float | None
    source_name: str
    source_url: str | None
    claim_type: Literal["observed", "derived", "inferred"]
```

Then each source returns:

- metadata
- raw payload summary
- normalized claims
- errors

The aggregator should merge claims by field precedence rules, not by source-name `if` statements.

### Better File Layout

Recommended structure:

```text
src/biradar/sources/enrichment/
  __init__.py
  orchestrator.py
  models.py
  registry.py
  bundesanzeiger.py
  github.py
  website.py
  handelsregister.py
```

Then:

- `orchestrator.py` runs enabled sources
- `registry.py` lists available source classes
- each source file owns only one adapter
- `models.py` owns `SourceClaim`, `SourceResult`, `EnrichmentResult`

This makes adding a source cheap and safe.

### Validation Standard For Enrichment

The current tests prove happy-path orchestration. They do not yet prove extensibility.

The next test level should include:

1. one test per source adapter
2. one orchestrator test with mixed source success/failure
3. one aggregator test for conflicting claims
4. one config-driven test that enables/disables sources without code changes

## 4. The Real Design Direction

If I were steering this repo, I would push it toward these interfaces:

### Acquisition

- `SourceFetcher`
- `PortalResponseParser`
- `RawPortalRecord`

### LLM

- `StructuredLLM`
- `ExtractionAgent`
- `RiskReviewAgent`

### Enrichment

- `EnrichmentSource`
- `SourceClaim`
- `EnrichmentOrchestrator`

This preserves the current architecture but gives each part a real substitution boundary.

## 5. Practical Next Steps

If you want the highest-value sequence, do it in this order:

1. Fix the portal parser architecture first.
   - If live acquisition is unstable, everything else is downstream noise.
2. Decouple LLM provider construction second.
   - This is a contained refactor with big long-term payoff.
3. Split enrichment into source modules and a registry third.
   - Do this before adding many more sources.
4. Only then expand product features.

## Bottom Line

Your instinct is correct on all three points.

- The parser is too shape-specific.
- The LLM integration is too provider-coupled.
- The enrichment design is not generic enough for easy growth.

The current implementation is acceptable as a working prototype. It is not the right long-term shape if you want:

- robust live scraping
- easy model switching
- incremental source expansion without turning one file into a maintenance trap
