# Testing Guide

This project is easiest to test with Docker Compose because the API depends on
PostgreSQL, Redis, MinIO, and a Celery worker.

## 1. Prerequisites

Install Docker Desktop and make sure this command works:

```bash
docker --version
```

## 2. Start The Project

From the project root:

```bash
make up
```

Leave this terminal running. In a second terminal, apply database migrations:

```bash
make migrate
```

Check that the API is alive:

```bash
make health
```

Expected response:

```json
{"status":"ok","service":"prikazy","environment":"local"}
```

Local base URL (override in Makefile: `make health API_BASE=http://127.0.0.1:8001`):

```text
http://localhost:8001
```

| Endpoint | URL |
|----------|-----|
| Health | http://localhost:8001/health |
| API docs | http://localhost:8001/docs |
| Sections | http://localhost:8001/sections |
| Viewer | http://localhost:8001/ |

## 3. Where To Put Test Files

Put local test documents in:

```text
samples/
```

Supported upload types are PDF, PNG, JPEG, TIFF, DOCX, and XLSX.

Example:

```text
samples/sample.pdf
```

## 4. Upload A Test Document

Use the helper command (default section: `prikaz`):

```bash
make upload SAMPLE=samples/sample.pdf
```

You can override metadata:

```bash
make upload SAMPLE=samples/sample.pdf DOC_TYPE=internal_contract COUNTERPARTY=ACME
```

Allowed `DOC_TYPE` values: `prikaz`, `internal_contract`, `external_contract`, `lna`.

The response should include `document_id`, `job_id`, and status `queued`.

## 5. Check Processing And Search

Watch API and worker logs:

```bash
make logs
```

Search OCR text:

```bash
make search SEARCH_Q=премирование
```

You can also list documents directly:

```bash
curl "http://localhost:8001/documents?tenant_id=00000000-0000-0000-0000-000000000001"
```

## 6. Run Automated Tests

Automated tests need Python 3.12 and project dependencies installed locally:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Or inside Docker:

```bash
docker compose exec app pytest
```

On macOS with the project in iCloud Drive, Docker may see stale files. Sync
explicitly before tests:

```bash
chmod +x scripts/docker-sync.sh
./scripts/docker-sync.sh
docker compose restart app worker
```

If you only want to smoke-test the running app, Docker Compose plus the upload
flow above is enough.
