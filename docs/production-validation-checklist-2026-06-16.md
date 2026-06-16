# Production Validation Checklist — 2026-06-16

## Scope

This is the concrete local validation gate used for the production-hardening pass on 2026-06-16.

## Validation List

- [x] `uv run ruff format --check src/biradar tests`
- [x] `uv run ruff check src/biradar tests`
- [x] `uv run pyright src/biradar`
- [x] `uv run pytest tests/unit --cov=src/biradar --cov-report=term-missing --timeout=30`
- [x] `uv run pytest tests/acceptance --cov=src/biradar --cov-report=term-missing --timeout=30`
- [x] `uv run pytest tests/e2e -m 'not live' --cov=src/biradar --cov-report=term-missing --timeout=60`
- [x] `uv run biradar --help`
- [x] `uv run biradar pipeline-check`
- [x] `uv run biradar mcp-info`
- [x] `make check`

## Notes

- `make check` now runs through `uv` using `UV_CACHE_DIR=.uv-cache`, so it works in a fresh repo-local environment without relying on globally installed `ruff`, `pyright`, or `pytest`.
- `pipeline-check` uses fixture input plus explicit deterministic stubs. It is a validation path, not the production runtime path.
- Live portal + live DeepSeek E2E was **not** rerun as part of this checklist. The local non-live gate is green.
- LangGraph checkpointing fell back to the in-memory saver in this environment because `langgraph.checkpoint.sqlite` was unavailable locally. Core pipeline execution still passed.
