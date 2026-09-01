# Behavior Changes Found During Refactor

Decision for this task: refactor without changing behavior. When a behavior change
would produce cleaner code, it is either applied deliberately (and noted here) or
reported here for a follow-up decision.

Format: one entry per finding — file, what the cleaner behavior would be, why the
refactor alone is not enough, and whether it was applied or deferred.

## Entries

### From the storage/repository.py review (deferred — falsy-value semantics kept verbatim)

1. `storage` (`find_covering_run`): runs with malformed `params_json` are silently
   skipped. Cleaner: log a warning. Deferred to keep behavior identical.
2. `storage` (`save_enrichment`): `str(website_status) if website_status else None`
   turns falsy values (`""`, `0`) into NULL. `is not None` would be cleaner.
3. `storage` (`log_event`): an empty dict `{}` is persisted as NULL, not `'{}'`.
4. `storage` (`upsert_raw_record` / `insert_evidence` / `insert_claim`): on a
   dedupe hit the new payload is silently dropped; `ON CONFLICT DO NOTHING` still
   returns the caller-supplied ID even though nothing was inserted.
5. `storage` (`upsert_candidate`): ON CONFLICT updates only `status`/`updated_at`;
   company-name/court changes on re-publication are silently ignored.
6. `storage` (`complete_run`): empty-string `error_json` marks the run "completed".
7. `storage` (`mark_exported`): no idempotency guard against double export.
8. `services/pipeline.py`: success, `_fail_result`, and outer-exception result
   dicts have three different key shapes; normalizing would change CLI/MCP
   payloads. Also: `run_pipeline` returns a plain dict rather than the
   `ResultEnvelope[T]` that AGENTS.md prescribes (MCP translates); converting is
   the standing deviation. Also: the outer `except Exception` returns
   `str(exc)` to the client, which is not a generic message.

### From writing the sources-layer tests (reported by the test agent, deferred)

9. `sources/enrichment/handelsregister.py`: the court regex `(?:Amtsgericht|AG)\s+…`
   has no word boundary before `AG`, so text like "…AG Berlin" anywhere in the
   page (e.g. inside a company name) yields a false `registry_court`; legal-form
   detection likewise scans the whole page rather than the company field.
10. `sources/enrichment/bundesanzeiger.py`: returns a populated-but-empty dict
    when nothing matched, so `enrich_candidate` counts the source as successful;
    the year regex grabs any `20XX`-like number anywhere in the page and keeps
    the 5 oldest rather than the newest reports.
11. `sources/enrichment/github.py`: rate-limit handling blocks synchronously for
    60 s and retries once; `languages` comes from an unordered set
    (`list(set)[:3]`), so output is nondeterministic.
12. `sources/enrichment/runtime.py`: `_http_get` treats any 403/400 as terminal
    (no retry) even when the response is not an anti-bot block.
13. `sources/enrichment/website.py`: the fallback slug can produce an invalid
    host like `https://-gmbh.de` for symbol-only company names; the first
    parseable response wins regardless of relevance.
14. `sources/official_portal.py`: `fetch_date_range` ends with
    `"records" if "records" in locals() else []` — dead code, `records` is always
    pre-initialized to `[]`.
15. `sources/enrichment/orchestrator.py`: the stubbed `_get_enrichment_config`
    governs source enablement, but the inter-source `time.sleep` reads the real
    cached runtime config, so the two config layers can disagree (real 0.3 s
    delays apply even when a stub config says 0.0).
16. `sources/enrichment/north_data.py`: the `count("/") < 2` link filter also
    excludes legitimate one-segment company detail pages.
