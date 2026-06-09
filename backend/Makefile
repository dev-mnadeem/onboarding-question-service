# Every target runs through `uv run`, which syncs the virtualenv from uv.lock
# first, so a clean checkout needs no activation step.
UV ?= uv
RUN := $(UV) run --extra dev --
PORT ?= 8000

.PHONY: help install lint lint-fix format check test run migrate makemigrations \
        superuser seed requirements compose-config clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Create the virtualenv from uv.lock
	$(UV) sync --extra dev

lint: ## Run the ruff linter
	$(RUN) ruff check .

lint-fix: ## Run the ruff linter and apply its fixes
	$(RUN) ruff check --fix .

format: ## Format the code with ruff
	$(RUN) ruff format .

check: ## Lint, check formatting and run Django's system checks
	$(RUN) ruff check .
	$(RUN) ruff format --check .
	$(RUN) python manage.py check
	$(RUN) python manage.py makemigrations --check --dry-run

test: ## Run the test suite
	LOG_LEVEL=ERROR $(RUN) python manage.py test

run: ## Start the development server (make run PORT=8001)
	$(RUN) python manage.py runserver $(PORT)

migrate: ## Apply migrations
	$(RUN) python manage.py migrate

makemigrations: ## Generate migrations from model changes
	$(RUN) python manage.py makemigrations

superuser: ## Create an admin account interactively
	$(RUN) python manage.py createsuperuser

seed: ## Fill an empty database with a demo questionnaire
	$(RUN) python manage.py seed_demo

requirements: ## Regenerate requirements.txt from uv.lock
	$(UV) export --no-hashes --no-dev --no-emit-project \
		--format requirements.txt -o requirements.txt

compose-config: ## Validate docker-compose.yml without building
	docker compose config --quiet && echo "docker-compose.yml is valid"

clean: ## Remove caches and build artefacts
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache staticfiles
