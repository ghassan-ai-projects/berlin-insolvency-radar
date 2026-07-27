.PHONY: check verify format format-check lint typecheck test test-integration test-acceptance test-e2e coverage audit pre-commit clean

# Conditional so CI can inherit the cache directory exported by astral-sh/setup-uv
# instead of writing to a repo-local cache the runner never restores.
UV_CACHE_DIR ?= .uv-cache
UV_RUN=UV_CACHE_DIR=$(UV_CACHE_DIR) uv run

# `verify` must stay a superset of what CI runs, or green locally means nothing.
check: verify
verify: pre-commit format-check lint typecheck test test-acceptance test-e2e coverage audit

pre-commit:
	$(UV_RUN) pre-commit run --all-files --show-diff-on-failure

format:
	$(UV_RUN) ruff format src/biradar tests

format-check:
	$(UV_RUN) ruff format --check src/biradar tests

lint:
	$(UV_RUN) ruff check src/biradar tests

typecheck:
	$(UV_RUN) pyright src/biradar

test:
	$(UV_RUN) pytest tests/unit --cov=src/biradar --cov-report=term-missing --timeout=30

test-integration:
	$(UV_RUN) pytest tests/integration --cov=src/biradar --cov-report=term-missing --timeout=30

test-acceptance:
	$(UV_RUN) pytest tests/acceptance --cov=src/biradar --cov-report=term-missing --timeout=30

test-e2e:
	$(UV_RUN) pytest tests/e2e -m "not live" --cov=src/biradar --cov-report=term-missing --timeout=60

# Single run across all three suites. The per-suite targets each overwrite
# .coverage, so only a combined run can be checked against the layer targets.
coverage:
	$(UV_RUN) pytest tests/unit tests/acceptance tests/e2e -m "not live" \
		--cov=src/biradar --cov-report=term-missing --cov-report=json --timeout=60
	$(UV_RUN) python scripts/check_coverage.py

# Audits the locked runtime dependency set. pip-audit runs via uvx so it stays
# out of the project's dependency tree.
audit:
	uv export --format requirements-txt --no-emit-project --no-dev -q -o .audit-requirements.txt
	uvx pip-audit -r .audit-requirements.txt --disable-pip
	rm -f .audit-requirements.txt

clean:
	rm -f .audit-requirements.txt coverage.json
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf data/radar.duckdb
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
