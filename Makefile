.PHONY: check phase0-check phase1-check format lint typecheck test test-integration test-acceptance test-e2e pre-commit clean

check: phase0-check
phase0-check: format lint typecheck test test-acceptance
phase1-check: format lint typecheck test test-acceptance test-e2e

pre-commit:
	pre-commit run --all-files

format:
	ruff format src/biradar tests

lint:
	ruff check src/biradar tests

typecheck:
	pyright src/biradar

test:
	pytest tests/unit --cov=src/biradar --cov-report=term-missing --timeout=30

test-integration:
	pytest tests/integration --cov=src/biradar --cov-report=term-missing --timeout=30

test-acceptance:
	pytest tests/acceptance --cov=src/biradar --cov-report=term-missing --timeout=30

test-e2e:
	pytest tests/e2e --cov=src/biradar --cov-report=term-missing --timeout=60

clean:
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf data/radar.duckdb
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
