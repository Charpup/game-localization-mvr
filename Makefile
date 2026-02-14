.PHONY: help install test test-unit test-integration test-benchmarks clean lint format docker-build docker-run

# Default target
help:
	@echo "Game Localization MVR - Available Commands:"
	@echo ""
	@echo "  install          - Install Python dependencies"
	@echo "  test             - Run all tests"
	@echo "  test-unit        - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-benchmarks  - Run benchmark tests"
	@echo "  clean            - Clean generated files"
	@echo "  lint             - Run linting checks"
	@echo "  format           - Format code with black"
	@echo "  docker-build     - Build Docker image"
	@echo "  docker-run       - Run Docker container"
	@echo "  pipeline         - Run full localization pipeline"
	@echo "  normalize        - Run normalization step"
	@echo "  translate        - Run translation step"
	@echo "  qa               - Run QA validation step"
	@echo "  export           - Run export step"

# Installation
install:
	pip install -r requirements.txt

# Testing
test: test-unit test-integration

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

test-benchmarks:
	pytest tests/benchmarks/ -v --tb=short

# Code Quality
lint:
	flake8 src/ tests/
	pylint src/

format:
	black src/ tests/
	isort src/ tests/

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ .pytest_cache/ .mypy_cache/ 2>/dev/null || true

# Docker
docker-build:
	docker build -t game-localization-mvr:latest .

docker-run:
	docker run --rm -it --env-file .env game-localization-mvr:latest

# Pipeline Steps
pipeline: normalize translate qa export

normalize:
	python -m src.scripts.normalize_guard --input examples/sample_input.csv --output data/normalized.csv

translate:
	python -m src.scripts.translate_llm --input data/normalized.csv --output data/translated.csv

qa:
	python -m src.scripts.qa_hard --input data/translated.csv --output data/qa_report.json

export:
	python -m src.scripts.rehydrate_export --input data/translated.csv --qa-report data/qa_report.json --output data/final_export.csv
