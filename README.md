# Prikazy

Самостоятельный проект для загрузки PDF и сканов приказов, хранения файлов в S3-совместимом хранилище, асинхронной OCR-обработки и полнотекстового поиска через PostgreSQL.

Отдельный репозиторий и инфраструктура — не связан с проектом «База данных» / `ocr-document-platform`.

## Текущий статус

MVP по спецификации `specs/prikazy.md`.

Реализовано:

- FastAPI: загрузка, чтение, повторная обработка, OCR, поиск.
- SQLAlchemy и миграции Alembic.
- Партиционированные таблицы `documents` и `ocr_results`.
- Полнотекстовый поиск PostgreSQL (`websearch_to_tsquery`, `ts_rank`, GIN).
- MinIO/S3 для бинарных файлов.
- Celery + Redis, учёт задач в БД.
- Подключаемый OCR-провайдер (по умолчанию `stub`).
- События обработки, `GET /health`.
- Docker Compose: API, worker, PostgreSQL, Redis, MinIO.

## Порты (чтобы не конфликтовать с «База данных»)

| Сервис     | URL / порт на хосте   |
|-----------|------------------------|
| API       | http://localhost:8001  |
| PostgreSQL| localhost:5433         |
| Redis     | localhost:6380         |
| MinIO API | http://localhost:9002  |
| MinIO UI  | http://localhost:9003  |

## Локальный запуск

```bash
cp .env.example .env
make up
```

Миграции:

```bash
make migrate
```

Проверка:

```bash
curl http://localhost:8001/health
```

Загрузка документа:

```bash
curl -X POST http://localhost:8001/documents/upload \
  -F "tenant_id=00000000-0000-0000-0000-000000000001" \
  -F "doc_type=invoice" \
  -F "counterparty_name=ACME" \
  -F "file=@./samples/sample.pdf;type=application/pdf"
```

Поиск:

```bash
curl "http://localhost:8001/search?tenant_id=00000000-0000-0000-0000-000000000001&q=invoice"
```

## Разработка

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8001
```

```bash
ruff check .
black --check .
pytest
```

## Архитектура

Файлы — в MinIO/S3; метаданные, OCR, поля, задачи и события — в PostgreSQL. OCR асинхронный через Celery. Для `.docx` / `.xlsx` используется прямое извлечение текста без OCR.

## Ограничения MVP

- Изоляция по `tenant_id` в query-параметрах; полноценная авторизация не реализована.
- Лимит загрузки по умолчанию 50 MB.
- Поиск только в PostgreSQL; граница репозитория готова к OpenSearch.
