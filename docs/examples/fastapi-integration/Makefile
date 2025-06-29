##@ General

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


##@ Dev
.PHONY:
start-services: ## Start the services locally
	docker compose up -d db

.PHONY:
stop-services: ## Stop the services running locally
	docker compose down --remove-orphans db

.PHONY: db-upgrade
db-upgrade: ## Run the database migrations
	uv run alembic upgrade head

.PHONY: run
run: db-upgrade ## Run the app
	uv run fastapi dev app/main.py

##@ Linting
.PHONY: ruff
ruff: ## Run ruff linter
	uv run ruff check app

.PHONY: black
black: ## Python code formatter
	uv run black --check app alembic

.PHONY: format
format: black ## Check formatting

.PHONY: type-check
type-check: ## Runs the type checker (mypy) against the app code
	uv run mypy app

.PHONY: lint
lint: ruff format type-check  ## Run linting checks

.PHONY: format-fix
format-fix: ## Run the auto-formatter
	uv run black app alembic

.PHONY: lint-fix
lint-fix: format-fix ## Run the linter and fix issues
	uv run ruff check app --fix

.PHONY: revision
revision: ## Create an Alembic revision with the provided message
	uv run alembic revision --autogenerate -m "$(msg)"

.PHONY: check
check: lint ## Run the linter and the unit tests

