# Unternehmensregister Integration Findings

**Date:** 2026-06-19  
**Status:** Live source verified manually, runtime adapter still pending

## What Was Verified Live

A real browser-driven lookup against `unternehmensregister.de` was completed for `Zalando SE`.

Observed live path:

1. Open `https://www.unternehmensregister.de/de/search/register-information`
2. Enter `Zalando SE`
3. Submit search
4. Follow `Registerinformationen anzeigen`
5. Observe result rows including:
   - `Zalando SE`
   - court `Amtsgericht Berlin (Charlottenburg)`
   - register number `HRB 158855`
   - status `Aktuell`

This confirms the source is operationally valuable and exposes exactly the kind of legal identity data BIRADAR needs.

## Why It Was Not Added As A Plain HTTP Adapter Yet

The public site is a Next.js application with client-side navigation and a generated `searchToken`.

What was observed:

- the HTML form is public and searchable
- direct browser navigation produces the real result table
- plain `httpx` fetches of the visible URLs do not expose the hydrated result rows
- the search flow emits tokenized result URLs only after the browser-driven path

Engineering conclusion:

- this is not a normal static HTML scraper target
- treating it like one would recreate the same fragility we just removed elsewhere

## Recommended Integration Boundary

If this source is promoted into production, do it in one of these shapes:

1. Browser-backed adapter with a narrow contract and aggressive caching.
2. Operator-assisted/manual lookup tool exposed separately from the default enrichment pass.
3. Dedicated acquisition worker for token/session generation, isolated from the normal fast HTTP source path.

The wrong choice would be:

- bolting brittle token guessing into the current synchronous HTTP enrichment loop

## Current Repo State

The source is now represented in config as a researched adapter candidate:

- `config/sources.yaml`
- `enrichment.sources.unternehmensregister.enabled: false`
- `integration_status: research_validated_pending_runtime_adapter`

That is deliberate. The product now acknowledges the source explicitly without pretending the implementation is cheaper than it is.
