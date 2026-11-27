# agenthalt — development targets. The runtime is stdlib-only; these are dev conveniences.

VENV ?= .venv
COV_MIN ?= 95
BOOTSTRAP ?= python3

# Use the project venv when it exists (local), else the interpreter on PATH (as in CI).
PYTHON ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)

.PHONY: setup lint typecheck test cov gate clean

setup: ## create the dev environment and install the package (editable) + dev extras
	$(BOOTSTRAP) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --quiet --upgrade pip
	$(VENV)/bin/python -m pip install --quiet -e ".[dev]"

lint: ## ruff, zero violations
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests

typecheck: ## mypy --strict
	$(PYTHON) -m mypy

test: ## run the test suite
	$(PYTHON) -m pytest

cov: ## run tests with coverage and enforce the milestone floor
	$(PYTHON) -m pytest --cov=agenthalt --cov-report=term-missing --cov-fail-under=$(COV_MIN)

gate: lint typecheck cov ## the standing milestone gate

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist src/*.egg-info
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
