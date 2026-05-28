# Prikazy

Самостоятельный проект для загрузки и хранения корпоративных документов: приказы, договоры (внутренние и внешние), ЛНА. Файлы — в S3-совместимом хранилище, асинхронная OCR-обработка и полнотекстовый поиск через PostgreSQL.

Отдельный репозиторий и инфраструктура — не связан с проектом «База данных» / `ocr-document-platform`.

## Текущий статус

MVP по спецификации `specs/prikazy.md`.

Реализовано:

- FastAPI: загрузка, чтение, повторная обработка, OCR, поиск, скачивание, веб-просмотр, AI-запросы к базе (YandexGPT).
- Портал сотрудников и админка с правами по разделам; AI доступен только при «Полном доступе».
- SQLAlchemy и миграции Alembic.
- Партиционированные таблицы `documents` и `ocr_results`.
- Полнотекстовый поиск PostgreSQL (`websearch_to_tsquery`, `ts_rank`, GIN).
- MinIO/S3 для бинарных файлов.
- Celery + Redis, учёт задач в БД.
- Подключаемый OCR-провайдер (по умолчанию `stub`).
- События обработки, `GET /health`.
- Docker Compose: API, worker, PostgreSQL, Redis, MinIO.

## Разделы документов

Документы делятся на разделы через поле `doc_type`. Список разделов:

| `doc_type` | Раздел |
|------------|--------|
| `prikaz` | Приказы |
| `internal_contract` | Договоры внутренние |
| `external_contract` | Договоры внешние |
| `lna` | ЛНА (локальные нормативные акты) |
| `technolog` | Технолог |
| `kadry` | Кадры |
| `incoming_correspondence` | Входящая корреспонденция |
| `outgoing_correspondence` | Исходящая корреспонденция |

Справочник разделов: `GET /sections`.

При загрузке `doc_type` обязателен. Без фильтра по разделу список и поиск работают **по всем разделам сразу** — удобно для общего поиска и будущей LLM-интеграции.

## Порты на локальной машине

Смещены относительно стандартных, чтобы не конфликтовать с проектом «База данных» / `ocr-document-platform`.

| Сервис     | URL / порт на хосте   |
|-----------|------------------------|
| API       | http://localhost:8001  |
| Swagger   | http://localhost:8001/docs |
| Разделы   | http://localhost:8001/sections |
| Портал    | http://localhost:8001/portal/ |
| Просмотр PDF | http://localhost:8001/viewer |
| PostgreSQL| localhost:5433         |
| Redis     | localhost:6380         |
| MinIO API | http://localhost:9002  |
| MinIO UI  | http://localhost:9003  |

В `.env` задайте `PUBLIC_API_BASE_URL=http://localhost:8001` — по этому адресу API отдаёт абсолютные `preview_url`, `download_url` и `viewer_url` в ответах `GET /documents`.

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

Загрузка документа (приказ):

```bash
curl -X POST http://localhost:8001/documents/upload \
  -F "tenant_id=00000000-0000-0000-0000-000000000001" \
  -F "doc_type=prikaz" \
  -F "title=Приказ о премировании" \
  -F "file=@./samples/sample.pdf;type=application/pdf"
```

Загрузка в другой раздел (например, внутренний договор):

```bash
curl -X POST http://localhost:8001/documents/upload \
  -F "tenant_id=00000000-0000-0000-0000-000000000001" \
  -F "doc_type=internal_contract" \
  -F "counterparty_name=Отдел продаж" \
  -F "file=@./samples/contract.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document"
```

Список документов одного раздела:

```bash
curl "http://localhost:8001/documents?tenant_id=00000000-0000-0000-0000-000000000001&doc_type=lna"
```

Список по нескольким разделам:

```bash
curl "http://localhost:8001/documents?tenant_id=00000000-0000-0000-0000-000000000001&doc_types=prikaz&doc_types=lna"
```

Поиск по всем разделам:

```bash
curl "http://localhost:8001/search?tenant_id=00000000-0000-0000-0000-000000000001&q=премирование"
```

Поиск только в договорах:

```bash
curl "http://localhost:8001/search?tenant_id=00000000-0000-0000-0000-000000000001&q=аренда&doc_types=internal_contract&doc_types=external_contract"
```

Просмотр и скачивание:

- Портал сотрудника: http://localhost:8001/portal/
- Просмотр оригинала: http://localhost:8001/viewer?tenant_id=00000000-0000-0000-0000-000000000001&document_id={uuid}
- В `GET /documents` и `GET /documents/{id}` — готовые ссылки: `viewer_url`, `preview_url`, `download_url` (с хостом из `PUBLIC_API_BASE_URL`).
- Файл inline: `GET /documents/{document_id}/file?tenant_id=...&disposition=inline`
- Скачивание: `GET /documents/{document_id}/download?tenant_id=...`

## AI-запросы к базе (Yandex Cloud)

Модель по умолчанию: **YandexGPT Lite** (`yandexgpt-lite/latest`) — оптимальный баланс цены и качества для function calling и работы с БД.

1. В [Yandex Cloud Console](https://console.yandex.cloud/) создайте API-ключ сервисного аккаунта с scope `yc.ai.foundationModels.execute`.
2. Укажите в `.env`: `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, `YANDEX_MODEL=yandexgpt-lite/latest`.
3. Войдите в портал под пользователем с правом **«Полный доступ»** к нужному разделу (или под администратором).
4. Запрос к AI (нужна сессия после логина):

```bash
curl -X POST "http://localhost:8001/ai/query" \
  -H "Content-Type: application/json" \
  -b "session=<cookie после логина>" \
  -d '{"question": "Сгруппируй приказы по типу документа"}'
```

Примеры вопросов: «Какие приказы у ответственного Иванов?», «Сколько документов по каждому статусу?».

LLM работает **только** с данными из PostgreSQL (без интернета). Результаты ограничены разделами, где у пользователя «Полный доступ».

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

- Портал с авторизацией и правами по разделам; AI только при «Полном доступе» к разделу.
- Лимит загрузки по умолчанию 50 MB.
- Поиск только в PostgreSQL; граница репозитория готова к OpenSearch.
