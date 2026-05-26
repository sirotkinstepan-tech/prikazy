TENANT_ID ?= 00000000-0000-0000-0000-000000000001
SAMPLE ?= samples/sample.pdf
DOC_TYPE ?= invoice
COUNTERPARTY ?= ACME

.PHONY: env up down migrate logs health upload search test lint format-check local-up local-down local-bootstrap

env:
	@test -f .env || cp .env.example .env

up: env
	docker compose up --build

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

logs:
	docker compose logs -f app worker

health:
	curl http://localhost:8000/health

upload:
	curl -X POST http://localhost:8000/documents/upload \
		-F "tenant_id=$(TENANT_ID)" \
		-F "doc_type=$(DOC_TYPE)" \
		-F "counterparty_name=$(COUNTERPARTY)" \
		-F "file=@./$(SAMPLE)"

search:
	curl "http://localhost:8000/search?tenant_id=$(TENANT_ID)&q=$(DOC_TYPE)"

test:
	pytest

lint:
	ruff check .

format-check:
	black --check .
