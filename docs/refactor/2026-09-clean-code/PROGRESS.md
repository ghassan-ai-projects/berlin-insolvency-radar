# Clean Code Refactor — Progress Bar

Task: apply clean-code principles (intent-revealing names, short single-purpose
functions, one level of abstraction per function, step-down rule) and break every
file down to a maximum of 250 lines.

Rules for this task:

- No behavior change. Anything where a behavior change would yield cleaner code is
  recorded in [BEHAVIOR-CHANGES.md](BEHAVIOR-CHANGES.md) instead of being applied silently.
- Tests are deferred to the end of the task (per task decision), then `make check` runs.
- Loop per file (ordered by line count, largest first):
  sub-agent analysis → change → review & fix → commit → update this bar.

## Bar

```
[██████████████████████████░░░░]  8 / 11  files over the 250-line cap processed
```

Coverage floor raised to >90% per layer mid-task (user decision). Layer status at
enforcement time: storage 99.4%, cli 98.3%, config 100%, utils 100%, sources 100%
(95 new tests), agents 96.3%, domain 98.1%, graph 93.5%, mcp 94.3%, output 98.7%,
services 92.3%, observability 100% — total 97%.

| # | File | Lines | Status |
|---|------|------:|--------|
| 1 | `src/biradar/storage/repository.py` | 907 | done (907 → 11 modules + facade, storage coverage 99.4%) |
| 2 | `src/biradar/services/pipeline.py` | 714 | done (714 → 9 modules + facade, max 195 lines) |
| 3 | `src/biradar/graph/pipeline_workflow.py` | 626 | done (626 → 10 modules + facade, max 226 lines) |
| 4 | `src/biradar/sources/official_portal.py` | 572 | done (572 → 9 modules + facade, max 158 lines) |
| 5 | `src/biradar/services/import_legacy.py` | 399 | done (399 → 9 modules + facade + storage/legacy_reader.py, max 231 lines; services 95.4%) |
| 6 | `src/biradar/services/issues.py` | 382 | done (382 → 7 modules + facade, max 158 lines; traversal-guard test added; services 95.7%) |
| 7 | `src/biradar/services/reviews.py` | 282 | done (282 → 5 modules + facade, max 172 lines; new unit tests, reviews 100% coverage; services 96.8%) |
| 8 | `src/biradar/storage/db.py` | 269 | done (269 → 4 modules + facade, max 213 lines; SQL byte-identical, registry replaces positional pairing; storage/db 100% coverage) |
| 9 | `src/biradar/mcp/server.py` | 262 | pending |
| 10 | `src/biradar/sources/enrichment/unternehmensregister.py` | 253 | pending |
| 11 | Sweep: all files < 250 lines | — | pending |
