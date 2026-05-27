API_BASE ?= http://localhost:8001
TENANT_ID ?= 00000000-0000-0000-0000-000000000001
SAMPLE ?= samples/sample.pdf
DOC_TYPE ?= prikaz
COUNTERPARTY ?= ACME

.PHONY: env up down migrate logs health upload search test lint format-check local-up local-down local-bootstrap

env:
	@test -f .env || cp .env.example .env

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

upload:
	curl -X POST $(API_BASE)/documents/upload \
		-F "tenant_id=$(TENANT_ID)" \
		-F "doc_type=$(DOC_TYPE)" \
		-F "counterparty_name=$(COUNTERPARTY)" \
		-F "file=@./$(SAMPLE)"

SEARCH_Q ?= премирование

search:
	curl --get "$(API_BASE)/search" \
		--data-urlencode "tenant_id=$(TENANT_ID)" \
		--data-urlencode "q=$(SEARCH_Q)"

test:
	docker compose exec -T app pytest

test-local:
	pytest

lint:
	ruff check .

format-check:
	black --check .
