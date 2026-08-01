# Prefer pyenv-local 3.11 (.python-version). Override: make install-dev PYTHON=/path/to/python3.11
PYTHON ?= python3
VENV ?= .venv
VENV_BIN := $(VENV)/bin
PYTEST := $(VENV_BIN)/pytest

.PHONY: help venv install-dev test test-cov coverage-html clean

help:
	@echo "Targets:"
	@echo "  make install-dev   Create .venv and install requirements-dev.txt"
	@echo "  make test          Run pytest"
	@echo "  make test-cov      Run pytest with coverage (app/lib, terminal report)"
	@echo "  make coverage-html Same as test-cov, plus htmlcov/ report"
	@echo "  make clean         Remove venv, caches, and coverage artifacts"
	@echo ""
	@echo "Requires Python 3.11 (see .python-version). Example:"
	@echo "  make install-dev PYTHON=$$HOME/.pyenv/versions/3.11.9/bin/python3.11"

venv:
	@PYVER=$$($(PYTHON) -c 'import sys; print("%d.%d" % sys.version_info[:2])'); \
	case "$$PYVER" in \
		3.11) ;; \
		*) echo "ERROR: need Python 3.11 (got $$PYVER from: $(PYTHON))" >&2; exit 1 ;; \
	esac
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip

install-dev: venv
	$(VENV_BIN)/pip install -r requirements-dev.txt

test: $(PYTEST)
	$(PYTEST) -q

test-cov: $(PYTEST)
	$(PYTEST) -q --cov=app.lib --cov-report=term-missing --cov-config=.coveragerc

coverage-html: $(PYTEST)
	$(PYTEST) -q --cov=app.lib --cov-report=term-missing --cov-report=html --cov-config=.coveragerc
	@echo "HTML report: htmlcov/index.html"

$(PYTEST):
	@echo "Missing $(PYTEST). Run: make install-dev" >&2
	@exit 1

clean:
	rm -rf $(VENV) .pytest_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -not -path './.git/*' -exec rm -rf {} + 2>/dev/null || true
