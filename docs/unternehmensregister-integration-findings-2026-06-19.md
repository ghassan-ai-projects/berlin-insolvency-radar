# Unternehmensregister Integration Findings

**Date:** 2026-06-19
**Status:** Live HTTP token adapter implemented and validated

## What Was Verified Live

Real lookups against `unternehmensregister.de` were completed for `Zalando SE`.

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

## Runtime HTTP Contract

The public site is a Next.js application with client-side navigation and a generated `searchToken`.

The implemented adapter uses the same public flow as the frontend:

1. `GET https://www.unternehmensregister.de/api/search-token`
2. `GET https://www.unternehmensregister.de/de/registerPortal`
3. Query parameters:
   - `companyName=<candidate name>`
   - `formType=REGISTER_INFORMATION`
   - `searchToken=<token from step 1>`
4. Follow redirects to `/de/registerinformationen`.
5. Extract the embedded `companies` array from the rendered Next/RSC payload.

Live HTTP validation on 2026-06-19 returned:

- company `Zalando SE`
- location `Berlin`
- EUID `DEF1103R.HRB158855B`
- court `Amtsgericht Berlin (Charlottenburg)`
- register number `HRB 158855`
- status `active`
- last update `2026-05-22`

## Implemented Boundary

The adapter is intentionally narrow:

- source module: `src/biradar/sources/enrichment/unternehmensregister.py`
- registration: normal enrichment source registry
- parser: balanced JSON-array extraction from the rendered payload, not table text scraping
- output fields: `legal_form`, `registry_court`, `registry_number`, `company_status`, `euid`, `last_update`, `location`, `source_url`
- failure mode: terminal HTTP blocks disable the source for the current run

## Operational Risks

- The adapter depends on an undocumented public frontend API.
- If the Next/RSC payload shape changes, unit tests still pass but live validation can fail.
- If the token endpoint starts enforcing stronger bot protection, this source should be disabled by config rather than retried aggressively.
- This adapter should remain enrichment-only; do not use it as the canonical insolvency acquisition source.

## Current Repo State

The source is now represented as an enabled runtime adapter:

- `config/sources.yaml`
- `enrichment.sources.unternehmensregister.enabled: true`
- `integration_status: live_http_token_adapter`

Validation coverage:

- deterministic unit coverage for payload parsing and field normalization
- acceptance coverage for config enablement
- live smoke validation against `Zalando SE`
