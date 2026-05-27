# Prikazy

Самостоятельный проект для загрузки PDF и сканов приказов, хранения файлов в S3-совместимом хранилище, асинхронной OCR-обработки и полнотекстового поиска через PostgreSQL.

Отдельный репозиторий и инфраструктура — не связан с проектом «База данных» / `ocr-document-platform`.

## Текущий статус

MVP по спецификации `specs/prikazy.md`.

Реализовано:

- FastAPI: загрузка, чтение, повторная обработка, OCR, поиск, AI-запросы к базе (YandexGPT).
- Авторизация AI по API-токенам с правом «Полный доступ».
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

AI-запрос к базе через Yandex Cloud (только для пользователей с правом «Полный доступ»):

1. В [Yandex Cloud Console](https://console.yandex.cloud/) создайте API-ключ сервисного аккаунта с scope `yc.ai.foundationModels.execute`.
2. Укажите в `.env`:
   - `YANDEX_API_KEY` — секрет API-ключа
   - `YANDEX_FOLDER_ID` — ID каталога
   - `YANDEX_MODEL=yandexgpt-lite/latest` — оптимальная модель по цене/качеству для работы с БД (function calling, низкая стоимость токенов)
3. Примените миграции и создайте пользователя с полным доступом:

```bash
make migrate
python scripts/create_api_token.py \
  --tenant-id 00000000-0000-0000-0000-000000000001 \
  --name "Администратор" \
  --access-level full_access
```

4. Запрос к AI:

```bash
curl -X POST "http://localhost:8001/ai/query?tenant_id=00000000-0000-0000-0000-000000000001" \
  -H "Authorization: Bearer <api_token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Сгруппируй приказы по типу документа"}'
```

Примеры вопросов:

- «Какие приказы у ответственного Иванов?»
- «Сколько документов по каждому статусу?»
- «Найди приказы про отпуск за 2024 год»

LLM работает **только** с данными из PostgreSQL через безопасные инструменты (без интернета и произвольного SQL).

Уровни доступа:

| Уровень | Код | AI-запросы |
|---------|-----|------------|
| Чтение | `read` | нет |
| Запись | `write` | нет |
| Полный доступ | `full_access` | да |

Для локальной разработки без токена можно временно выставить `AUTH_REQUIRED_FOR_AI=false`.

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

- Изоляция по `tenant_id`; AI защищён API-токенами с правом «Полный доступ», остальные эндпоинты пока без авторизации.
- Лимит загрузки по умолчанию 50 MB.
- Поиск только в PostgreSQL; граница репозитория готова к OpenSearch.
