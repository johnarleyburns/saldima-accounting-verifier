.PHONY: sync test test-core lint typecheck format report

sync:
	uv sync --all-extras

test:
	uv run pytest

test-core:
	uv run pytest tests/unit tests/invariants tests/integration

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy reference runner adapters

report:
	uv run python -m runner.cli report
