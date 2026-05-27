API_BASE ?= http://localhost:8001
TENANT_ID ?= 00000000-0000-0000-0000-000000000001
SAMPLE ?= samples/sample.pdf
DOC_TYPE ?= prikaz
COUNTERPARTY ?= ACME
COOKIE_JAR ?= .api-cookies.txt
CSRF_FILE ?= .api-csrf-token
API_EMAIL ?= admin@example.com
API_PASSWORD ?= admin123

.PHONY: env up down migrate logs health upload search test lint format-check local-up local-down local-bootstrap api-login api-curl-upload api-curl-search seed setup setup-yandex

env:
	@test -f .env || cp .env.example .env

setup:
	chmod +x scripts/setup-project.sh scripts/setup-yandex-llm.sh
	./scripts/setup-project.sh

setup-yandex:
	chmod +x scripts/setup-yandex-llm.sh
	./scripts/setup-yandex-llm.sh

up: env
	DOCKER_BUILDKIT=0 docker compose up --build

down:
	docker compose down

local-bootstrap:
	./scripts/bootstrap-local.sh

local-up:
	./scripts/local-dev-up.sh

local-down:
	./scripts/local-dev-down.sh

migrate:
	docker compose exec app alembic upgrade head

seed:
	docker compose exec app python scripts/seed_users.py

logs:
	docker compose logs -f app worker

health:
	curl $(API_BASE)/health

api-login:
	chmod +x scripts/api-session.sh
	API_BASE=$(API_BASE) EMAIL=$(API_EMAIL) PASSWORD=$(API_PASSWORD) \
		COOKIE_JAR=$(COOKIE_JAR) CSRF_FILE=$(CSRF_FILE) ./scripts/api-session.sh

api-curl-upload: api-login
	curl -X POST $(API_BASE)/documents/upload \
		-b $(COOKIE_JAR) \
		-H "X-CSRF-Token: $$(cat $(CSRF_FILE))" \
		-F "doc_type=$(DOC_TYPE)" \
		-F "counterparty_name=$(COUNTERPARTY)" \
		-F "file=@./$(SAMPLE)"

upload: api-curl-upload

SEARCH_Q ?= премирование

api-curl-search: api-login
	curl --get "$(API_BASE)/search" \
		-b $(COOKIE_JAR) \
		--data-urlencode "q=$(SEARCH_Q)"

search: api-curl-search

test:
	docker compose exec -T app pytest

test-local:
	pytest

lint:
	ruff check .

format-check:
	black --check .
