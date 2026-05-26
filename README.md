# OCR Document Platform

Production-oriented MVP for uploading PDF/scanned documents, storing binaries in S3-compatible object storage, processing OCR asynchronously, and searching OCR text through PostgreSQL full-text search.

## Current Status

The MVP follows `specs/ocr-document-platform.md`.

Implemented so far:

- FastAPI API with document upload/read/reprocess/OCR/search endpoints.
- SQLAlchemy models and Alembic migrations.
- PostgreSQL partitioned tables for `documents` and `ocr_results`.
- PostgreSQL full-text search with `websearch_to_tsquery`, `ts_rank`, and GIN indexes.
- MinIO/S3 object storage integration.
- Celery worker with Redis broker and durable application-level job tracking.
- Pluggable OCR provider interface with deterministic stub provider.
- Processing audit events.
- Environment-based configuration through `.env`.
- `GET /health`.
- Docker Compose services for API, worker, PostgreSQL, Redis, and MinIO.

## Local Setup

Create a local environment file:

```bash
cp .env.example .env
```

Start local infrastructure and application containers:

```bash
docker compose up --build
```

Apply migrations:

```bash
docker compose exec app alembic upgrade head
```

Healthcheck:

```bash
curl http://localhost:8000/health
```

Upload a document:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "tenant_id=00000000-0000-0000-0000-000000000001" \
  -F "doc_type=invoice" \
  -F "counterparty_name=ACME" \
  -F "file=@./sample.pdf;type=application/pdf"
```

Search OCR text:

```bash
curl "http://localhost:8000/search?tenant_id=00000000-0000-0000-0000-000000000001&q=invoice"
```

## Development Commands

Install dependencies locally:

```bash
pip install -e ".[dev]"
```

Run the API locally:

```bash
uvicorn app.main:app --reload
```

Run lint and format checks:

```bash
ruff check .
black --check .
```

Run tests:

```bash
pytest
```

## Architecture Notes

Binary files are stored in MinIO/S3. PostgreSQL stores object references, metadata, OCR output, extracted fields, processing jobs, and events.

OCR is asynchronous. Upload creates a document and `processing_jobs` row, then enqueues `app.workers.tasks.process_ocr_job`. The worker downloads the file from object storage, extracts text from Word/Excel directly or runs the configured OCR provider for PDF/images/scans, persists `ocr_results`, and updates statuses/events.

The default OCR provider is `stub`, which makes local development and tests deterministic. A real engine such as Tesseract can be added behind `app.services.ocr_provider.OcrProvider`. Word (`.docx`) and Excel (`.xlsx`) files bypass OCR and use direct text extraction via `python-docx` and `openpyxl`.

## Important MVP Limits

- Tenant isolation is enforced by `tenant_id` query parameters. Production authentication/authorization is still required.
- Uploads are read into memory with a default 50 MB limit.
- Search uses PostgreSQL for MVP; the repository boundary is ready for future OpenSearch indexing.

