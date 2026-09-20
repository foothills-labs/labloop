.PHONY: setup metadata check

setup:
	uv sync --locked --extra dev

metadata:
	uv run --python 3.12 --locked --script .plicara/check.py

check: metadata
	uv lock --check
	uv run --locked --extra dev ruff check src tests
	uv run --locked --extra dev mypy
	uv run --locked --extra dev python -m pytest -q
