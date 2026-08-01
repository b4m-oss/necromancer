# Prefer pyenv-local 3.11 (.python-version). Override: make install-dev PYTHON=/path/to/python3.11
PYTHON ?= python3
VENV ?= .venv
VENV_BIN := $(VENV)/bin
PYTEST := $(VENV_BIN)/pytest
DOCKER_COMPOSE ?= docker compose

.PHONY: help venv install-dev install-pi test test-cov coverage-html docker-build docker-test clean

help:
	@echo "Targets:"
	@echo "  make install-dev    Create .venv and pip install -e \".[dev]\""
	@echo "  make install-pi     Run ./install.sh (Raspberry Pi deploy via app/install.sh)"
	@echo "  make test           Run pytest on host"
	@echo "  make test-cov       Run pytest with coverage (app/lib, terminal report)"
	@echo "  make coverage-html  Same as test-cov, plus htmlcov/ report"
	@echo "  make docker-build   Build the Python 3.11 dev image"
	@echo "  make docker-test    Run pytest (with coverage) inside Docker"
	@echo "  make clean          Remove venv, caches, and coverage artifacts"
	@echo ""
	@echo "Requires Python 3.11 (see .python-version). Example:"
	@echo "  make install-dev PYTHON=$$HOME/.pyenv/versions/3.11.9/bin/python3.11"
	@echo ""
	@echo "Docker (no local venv needed):"
	@echo "  make docker-build && make docker-test"

venv:
	@PYVER=$$($(PYTHON) -c 'import sys; print("%d.%d" % sys.version_info[:2])'); \
	case "$$PYVER" in \
		3.11) ;; \
		*) echo "ERROR: need Python 3.11 (got $$PYVER from: $(PYTHON))" >&2; exit 1 ;; \
	esac
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip

install-dev: venv
	$(VENV_BIN)/pip install -e ".[dev]"

install-pi:
	./install.sh

test: $(PYTEST)
	$(PYTEST) -q

test-cov: $(PYTEST)
	$(PYTEST) -q --cov=app.lib --cov-report=term-missing --cov-config=.coveragerc

coverage-html: $(PYTEST)
	$(PYTEST) -q --cov=app.lib --cov-report=term-missing --cov-report=html --cov-config=.coveragerc
	@echo "HTML report: htmlcov/index.html"

docker-build:
	$(DOCKER_COMPOSE) build

docker-test: docker-build
	$(DOCKER_COMPOSE) run --rm dev \
		sh -c "pip install -q -e '.[dev]' && pytest -q --cov=app.lib --cov-report=term-missing --cov-config=.coveragerc"

$(PYTEST):
	@echo "Missing $(PYTEST). Run: make install-dev" >&2
	@exit 1

clean:
	rm -rf $(VENV) .pytest_cache htmlcov .coverage coverage.xml *.egg-info build dist
	find . -type d -name __pycache__ -not -path './.git/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -not -path './.git/*' -exec rm -rf {} + 2>/dev/null || true
