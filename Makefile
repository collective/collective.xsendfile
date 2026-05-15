.PHONY: help venv install test lint format coverage clean

VENV := .venv
BIN := $(VENV)/bin
PYTHON ?= python3
PACKAGE := collective.xsendfile
PACKAGE_DIR := collective/xsendfile

help:
	@echo "Targets:"
	@echo "  install   Create $(VENV) (if missing) and install package with test+lint extras"
	@echo "  test      Run the test suite with zope.testrunner"
	@echo "  coverage  Run tests under coverage and print a report"
	@echo "  lint      Run flake8, black --check, and zpretty --check"
	@echo "  format    Auto-format with black and zpretty"
	@echo "  clean     Remove caches and coverage artefacts"

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

venv: $(BIN)/python

install: venv
	$(BIN)/pip install -e ".[test,lint]"
	$(BIN)/pip install 'setuptools<81'  # Plone deps still import pkg_resources

test:
	$(BIN)/zope-testrunner --test-path=. -m $(PACKAGE)

coverage:
	$(BIN)/coverage run --source=$(PACKAGE) \
		$(BIN)/zope-testrunner --test-path=. -m $(PACKAGE)
	$(BIN)/coverage report -m
	$(BIN)/coverage html

lint:
	$(BIN)/flake8 $(PACKAGE_DIR)
	$(BIN)/black --check $(PACKAGE_DIR)
	$(BIN)/zpretty --check $(shell find $(PACKAGE_DIR) -name '*.zcml' -o -name '*.xml')

format:
	$(BIN)/black $(PACKAGE_DIR)
	$(BIN)/zpretty -i $(shell find $(PACKAGE_DIR) -name '*.zcml' -o -name '*.xml')

clean:
	rm -rf .coverage htmlcov .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
