.PHONY: help lint format install-dev serve test coverage langgraph-dev lint-frontend

help: ## Show this help message
	@echo "Deer Flow - Available Make Targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage: make <target>"

install-dev: ## Install development dependencies
	cd backend && uv pip install -e ".[dev]" && uv pip install -e ".[test]"

format: ## Format code using ruff
	cd backend && uv run ruff format --config pyproject.toml .

lint: ## Lint and fix code using ruff
	cd backend && uv run ruff check --fix --select I --config pyproject.toml .

lint-frontend: ## Lint frontend code and check build
	cd web && pnpm install --frozen-lockfile
	cd web && pnpm lint
	cd web && pnpm typecheck
	cd web && pnpm build

serve: ## Start development server with reload
	cd backend && uv run server.py --reload

test: ## Run tests with pytest
	cd backend && uv run pytest tests/

langgraph-dev: ## Start langgraph development server
	cd backend && uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev --allow-blocking

coverage: ## Run tests with coverage report
	cd backend && uv run pytest --cov=src tests/ --cov-report=term-missing --cov-report=xml