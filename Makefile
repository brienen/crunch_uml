PYTHON_BINARY := python3
VIRTUAL_ENV := .venv
VIRTUAL_BIN := $(VIRTUAL_ENV)/bin
crunch_uml := crunch_uml
TEST_DIR := test

## help - Display help about make targets for this Makefile
help:
	@cat Makefile | grep '^## ' --color=never | cut -c4- | sed -e "`printf 's/ - /\t- /;'`" | column -s "`printf '\t'`" -t

## build - Builds the project in preparation for release
build:
	$(VIRTUAL_BIN)/python -m build

## coverage - Test the project and generate an HTML coverage report
coverage:
	$(VIRTUAL_BIN)/pytest --cov=$(crunch_uml) --cov-branch --cov-report=html --cov-report=lcov --cov-report=term-missing

## clean - Remove the virtual environment and clear out .pyc files
clean:
	rm -rf dist *.egg-info .coverage build .pytest_cache
	find . -name '*.pyc' -delete

## black - Runs the Black Python formatter against the project
black:
	$(VIRTUAL_BIN)/black $(crunch_uml)/ $(TEST_DIR)/

## black-check - Checks if the project is formatted correctly against the Black rules
black-check:
	$(VIRTUAL_BIN)/black $(crunch_uml)/ $(TEST_DIR)/ --check

## format - Runs all formatting tools against the project
format: black isort lint mypy

## format-check - Checks if the project is formatted correctly against all formatting rules
format-check: black-check isort-check lint mypy

## install - Install the project locally
install:
	$(PYTHON_BINARY) -m venv $(VIRTUAL_ENV)
	$(VIRTUAL_BIN)/pip install --upgrade setuptools wheel pip
	$(VIRTUAL_BIN)/pip install -e ."[dev]" --no-use-pep517

## isort - Sorts imports throughout the project
isort:
	$(VIRTUAL_BIN)/isort $(crunch_uml)/ $(TEST_DIR)/

## isort-check - Checks that imports throughout the project are sorted correctly
isort-check:
	$(VIRTUAL_BIN)/isort $(crunch_uml)/ $(TEST_DIR)/ --check-only

## lint - Lint the project
lint:
	$(VIRTUAL_BIN)/flake8 $(crunch_uml)/ $(TEST_DIR)/

## mypy - Run mypy type checking on the project
mypy:
	$(VIRTUAL_BIN)/mypy $(crunch_uml)/ $(TEST_DIR)/

## test - Test the project
test:
	$(VIRTUAL_BIN)/pytest -m "not slow"

## test - Test the project
test-all:
	$(VIRTUAL_BIN)/pytest


.PHONY: help build coverage clean black black-check format format-check install isort isort-check lint mypy test
