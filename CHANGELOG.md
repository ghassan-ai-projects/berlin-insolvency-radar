# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows semantic versioning from its public release line.

## [Unreleased]

Pre-release development.

### Added

- Phase 0: MCP-first foundation with DuckDB persistence, LangGraph health workflow, 8 MCP tools
- Phase 1: Legacy insolvency data import, editorial review workflow, 20 acceptance tests
- Phase 2: Fully agentic pipeline — JSF official portal scraping, LLM extraction (DeepSeek),
  enrichment, deterministic scoring, risk review, Markdown export
- 28 unit tests, 20 acceptance tests, 6 E2E tests, 81% coverage
- Open-source governance: AGENTS.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, SUPPORT.md
- Structured public documentation under `documentation/`
- `--max-records N` CLI flag on `pipeline-run` to cap raw records for quick validation runs

### Fixed

- DeepSeek `with_structured_output` removed — caused 400 errors on every LLM call
- Null `evidence_snippets` values now sanitized before Pydantic validation
- Scoring baseline raised (`speed_of_action` 2→3) to handle missing `proceeding_stage` in portal data
- Risk review draft thesis now includes extraction evidence, preventing false rejections
- Portal fixture updated from JSF XML to live HTML format with `table#tbl_ergebnis`
- Bridge files for Claude, Gemini, and GitHub Copilot
