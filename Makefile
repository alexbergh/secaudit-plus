.PHONY: help install test lint format clean build docker run-audit

# Default target
help:
	@echo "SecAudit+ Makefile Commands:"
	@echo ""
	@echo "  make install       - Install dependencies and package"
	@echo "  make test          - Run tests with coverage"
	@echo "  make lint          - Run all linters"
	@echo "  make format        - Format code with black and isort"
	@echo "  make security      - Run security scans"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make build         - Build distribution packages"
	@echo "  make docker        - Build Docker image"
	@echo "  make docker-test   - Run tests in Docker"
	@echo "  make run-audit     - Run sample audit"
	@echo "  make pre-commit    - Install pre-commit hooks"
	@echo ""

# Installation
install:
	python -m pip install --upgrade pip
	pip install -e .
	pip install -r requirements.txt

install-dev: install
	pip install pre-commit pytest-cov bandit safety black isort

# Testing
test:
	pytest --cov=modules --cov=secaudit --cov=seclib --cov=utils \
	       --cov-report=term-missing \
	       --cov-report=html \
	       --cov-report=xml \
	       -v

test-fast:
	pytest -v -x

test-verbose:
	pytest -vv -s

# Linting
lint: lint-flake8 lint-mypy lint-yaml

lint-flake8:
	flake8 modules secaudit utils tests --max-line-length=120 --exclude __init__.py

lint-mypy:
	mypy modules secaudit utils tests --ignore-missing-imports

lint-yaml:
	yamllint profiles .github/workflows

# Formatting
format:
	black modules secaudit utils tests --line-length=120
	isort modules secaudit utils tests --profile=black --line-length=120

format-check:
	black modules secaudit utils tests --check --line-length=120
	isort modules secaudit utils tests --check-only --profile=black --line-length=120

# Security
security: security-bandit security-safety

security-bandit:
	bandit -r modules secaudit utils -ll

security-safety:
	safety check --json || true
	safety check

security-gitleaks:
	gitleaks detect --source . --verbose

# Cleaning
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete

# Building
build: clean
	python -m build

build-check:
	python -m build
	twine check dist/*

# Docker
docker:
	docker build -t secaudit-plus:latest .

docker-dev:
	docker-compose build secaudit-dev

docker-test:
	docker-compose run --rm secaudit-test

docker-run:
	docker-compose run --rm secaudit

# Running
run-audit:
	secaudit audit --profile profiles/base/linux.yml --level baseline

run-validate:
	secaudit validate --profile profiles/base/linux.yml --strict

run-info:
	secaudit --info

# Pre-commit
pre-commit:
	pre-commit install
	pre-commit install --hook-type commit-msg

pre-commit-run:
	pre-commit run --all-files

# CI simulation
ci: lint test security build-check
	@echo "✅ All CI checks passed!"

# Release preparation
release-check: ci
	@echo "Checking version consistency..."
	@grep -q "version = \"$(VERSION)\"" pyproject.toml || (echo "❌ Version mismatch in pyproject.toml" && exit 1)
	@echo "✅ Ready for release $(VERSION)"

# Documentation
docs:
	@echo "Documentation generation not yet implemented"

# All checks
all: format lint test security build
	@echo "✅ All checks completed successfully!"
