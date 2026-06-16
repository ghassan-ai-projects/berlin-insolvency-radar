.PHONY: check verify format format-check lint typecheck test test-integration test-acceptance test-e2e pre-commit clean

UV_RUN=UV_CACHE_DIR=.uv-cache uv run

check: verify
verify: format-check lint typecheck test test-acceptance test-e2e

pre-commit:
	$(UV_RUN) pre-commit run --all-files

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

clean:
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf data/radar.duckdb
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
