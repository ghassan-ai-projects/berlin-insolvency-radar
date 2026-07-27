# Contributing

## Scope

Contributions are welcome for code, tests, documentation, prompt assets, and integration guidance.

## Before You Start

- read [README.md](README.md)
- read [documentation/README.md](documentation/README.md)
- read [AGENTS.md](AGENTS.md) if you are contributing with a coding agent

## Development Setup

```bash
uv sync --extra dev
cp .env.example .env
# Edit .env with your DEEPSEEK_API_KEY
```

## Contribution Rules

- preserve the 6-layer architecture (see [AGENTS.md](AGENTS.md))
- keep changes scoped and coherent
- add or update tests with code changes
- update documentation when behavior or public contracts change
- do not rewrite existing database migrations; add new ones
- all MCP tools must use Pydantic-validated inputs
- never commit secrets or API keys

## Quality Gate

Run before opening a PR:

```bash
make check
```

This runs pre-commit, format, lint, typecheck, and the unit, acceptance, and
non-live E2E suites. CI runs the same Make targets, so a green `make check` is a
green pipeline.

## Pull Request Expectations

Each pull request should include:

- a clear problem statement
- the chosen approach
- any contract or migration impact
- test coverage for behavior changes
- documentation updates if the change affects users or contributors

## Documentation Contributions

The tracked public docs live in `documentation/`. The `docs/` directory contains internal development docs (plans, reviews, research) and should not receive new public-facing documentation.

## Conduct

By participating, you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
