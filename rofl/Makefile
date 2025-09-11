# ROFL Paymaster Makefile
# Python-based development tools for testing and code quality

.PHONY: help test test-models test-verbose test-coverage install lint format type-check clean

# Default target
help:
	@echo "Available commands:"
	@echo "  make test                  - Run all tests"
	@echo "  make test-models           - Run only model tests"
	@echo "  make test-verbose         - Run tests with verbose output"
	@echo "  make test-coverage        - Run tests with coverage report"
	@echo "  make install               - Install dependencies (editable install)"
	@echo "  make lint                  - Run code linting (flake8)"
	@echo "  make format                - Format code (black)"
	@echo "  make type-check            - Run type checking (mypy)"
	@echo "  make clean                 - Clean up cache files"

# Test commands
test:
	python3 -m pytest

test-models:
	python3 -m pytest tests/test_models.py

test-verbose:
	python3 -m pytest -v

test-coverage:
	python3 -m pytest --cov=src/rofl_paymaster --cov-report=html --cov-report=term

# Development setup
install:
	pip install -e ".[dev]"

# Code quality
lint:
	flake8 src/ tests/

format:
	black src/ tests/

type-check:
	mypy src/

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true