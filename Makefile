.PHONY: check phase0-check phase1-check format lint typecheck test test-integration test-acceptance clean

check: phase0-check
phase0-check: format lint typecheck test test-acceptance
phase1-check: format lint typecheck test test-acceptance

format:
	ruff format src/biradar tests

lint:
	ruff check src/biradar tests

typecheck:
	pyright src/biradar

test:
	pytest tests/unit --cov=src/biradar --cov-report=term-missing

test-integration:
	pytest tests/integration --cov=src/biradar --cov-report=term-missing

test-acceptance:
	pytest tests/acceptance --cov=src/biradar --cov-report=term-missing

clean:
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf data/radar.duckdb
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
