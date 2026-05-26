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

The interactive API docs are available at:

```text
http://localhost:8001/docs
```

## 3. Where To Put Test Files

Put local test documents in:

```text
samples/
```

Supported upload types are PDF, PNG, JPEG, and TIFF.

Example:

```text
samples/invoice.pdf
```

## 4. Upload A Test Document

Use the helper command:

```bash
make upload SAMPLE=samples/invoice.pdf
```

You can override metadata:

```bash
make upload SAMPLE=samples/invoice.pdf DOC_TYPE=invoice COUNTERPARTY=ACME
```

The response should include `document_id`, `job_id`, and status `queued`.

## 5. Check Processing And Search

Watch API and worker logs:

```bash
make logs
```

Search OCR text:

```bash
make search DOC_TYPE=invoice
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

If you only want to smoke-test the running app, Docker Compose plus the upload
flow above is enough.
