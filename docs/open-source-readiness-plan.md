# Open-Source Readiness Plan — Berlin Insolvency Radar

**Date:** 2026-06-16
**Reference project:** ALMS (`/Users/ghassan/my-projects/alms`)

## Overview

Replicate ALMS's open-source patterns: AGENTS.md bridge system, governance files,
CI, structured `documentation/` folder, and a project-level README rewrite.

## Phase 1: Agent Configuration Files

ALMS uses a canonical `AGENTS.md` + thin bridge files pattern. All bridge files point to `AGENTS.md`.

| File | Action |
|------|--------|
| `AGENTS.md` | **Create.** Python-specific canonical instructions. Covers: project identity, coding conventions, test mandate, quality gates, commit style, agent workflow. Adapted from ALMS but for Python/uv/pytest/ruff/pyright. |
| `CLAUDE.md` | **Create.** Thin bridge: `@AGENTS.md` + Claude-specific note. |
| `GEMINI.md` | **Create.** Thin bridge: references AGENTS.md, suggests contextFileName config. |
| `.github/copilot-instructions.md` | **Create.** Thin bridge: references AGENTS.md, keep durable rules in AGENTS.md. |

## Phase 2: Open-Source Governance Files

| File | Action |
|------|--------|
| `CONTRIBUTING.md` | **Create.** Modeled on ALMS. Scope, setup (`uv sync --extra dev`), rules (type-safe, tests, audit), quality gate (`make check`), PR expectations, conduct reference. |
| `CODE_OF_CONDUCT.md` | **Create.** Same custom short format as ALMS. Standard of respect, unacceptable behavior list, enforcement, private reporting email. |
| `SECURITY.md` | **Create.** Supported release line, private vulnerability reporting, security expectations for API key management. |
| `CHANGELOG.md` | **Create.** Keep a Changelog format. Entry for current state. |
| `SUPPORT.md` | **Create.** Documentation-first support policy, issue template guidance. |

## Phase 3: CI Pipeline

| File | Action |
|------|--------|
| `.github/workflows/ci.yml` | **Create.** Python CI: setup uv, run `make check` (format, lint, typecheck, test, test-acceptance, test-e2e), coverage upload. |
| `.editorconfig` | **Create.** Python defaults: indent_size=4, charset=utf-8, trim trailing whitespace. |

## Phase 4: `documentation/` Folder

Create a tracked `documentation/` folder (ALMS pattern: tracked public docs separate from legacy `docs/`).

Move existing docs from `docs/` that are appropriate for public use:

**Start Here:**
- `documentation/product-overview.md` — adapted from `docs/README.md` and `docs/HANDOFF-TO-CODING-AGENT.md`
- `documentation/how-it-works.md` — adapted from `docs/strategy/application-architecture.md`
- `documentation/getting-started.md` — adapted from `README.md` quick start

**Reference:**
- `documentation/architecture.md` — adapted from `docs/strategy/application-architecture.md`
- `documentation/mcp-api.md` — adapted from `docs/strategy/mcp-interface.md`
- `documentation/configuration.md` — from `docs/CONVENTIONS.md` config section + `config/`
- `documentation/scoring-model.md` — adapted from `docs/strategy/scoring-model.md`
- `documentation/data-sources.md` — adapted from `docs/research/data-sources.md`
- `documentation/legal-and-compliance.md` — adapted from `docs/research/legal.md`
- `documentation/testing-standards.md` — adapted from `docs/strategy/testing-and-coding-standards.md`

**Governance:**
- `documentation/security-model.md` — adapted from `docs/code-quality-review.md` security findings

**Index:**
- `documentation/README.md` — structured index (Start Here, Reference, Governance)

## Phase 5: Rewrite README.md

Follow ALMS README structure:
1. Title: `# Berlin Insolvency Radar`
2. Tagline: What it is, its value proposition
3. `## Why BIRADAR` — the problem it solves
4. `## What It Does` — feature list
5. `## Quick Start` — `uv sync`, `make check`, MCP server start
6. `## Documentation` — links to all `documentation/` files
7. `## Open Source` — links to governance files + MIT rationale
8. `## Status` — current phase

## Phase 6: Verify

- Run `make check` to ensure nothing is broken
- Verify all links in README and documentation index are correct

---

## Files to Create (20 files)

```
AGENTS.md
CLAUDE.md
GEMINI.md
CHANGELOG.md
CODE_OF_CONDUCT.md
CONTRIBUTING.md
SECURITY.md
SUPPORT.md
.editorconfig
.github/copilot-instructions.md
.github/workflows/ci.yml
documentation/README.md
documentation/product-overview.md
documentation/how-it-works.md
documentation/getting-started.md
documentation/architecture.md
documentation/mcp-api.md
documentation/configuration.md
documentation/scoring-model.md
documentation/data-sources.md
documentation/legal-and-compliance.md
documentation/testing-standards.md
documentation/security-model.md
```

## Files to Modify (1 file)

```
README.md — full rewrite
```
