.PHONY: install local clean test lint

install:
	uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"

local:
	cp -n .env.example .env || true
	uv run str-assistant

clean:
	rm -rf .venv __pycache__ dist *.egg-info

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check . && uv run ruff format --check .
