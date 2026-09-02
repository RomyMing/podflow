# PodFlow backend developer shortcuts. Run from podcast_translator/.
# Frontend tasks live under frontend/ (npm ci / npm run dev / npm run build).

.PHONY: help install test test-file lint typecheck check fmt clean-voices clean-s3

help:
	@echo "PodFlow backend make targets:"
	@echo "  make install      Install backend + dev deps (pip install -e .[dev])"
	@echo "  make test         Run the full backend test suite (pytest)"
	@echo "  make test-file F=path::test   Run a single test or file"
	@echo "  make lint         ruff check src tests (CI gate)"
	@echo "  make typecheck    mypy src"
	@echo "  make check        lint + typecheck + test"
	@echo "  make fmt          ruff format src tests"
	@echo "  make clean-voices Delete expired ElevenLabs voices (retention sweep)"
	@echo "  make clean-s3     Delete intermediate S3 artifacts for old completed tasks"

install:
	pip install -e .[dev]

test:
	pytest

# Usage: make test-file F=tests/unit/test_services/test_task_service.py
test-file:
	pytest $(F)

lint:
	ruff check src tests

typecheck:
	mypy src

check: lint typecheck test

fmt:
	ruff format src tests

clean-voices:
	python -m scripts.cleanup_voices

clean-s3:
	python -m scripts.cleanup_s3
