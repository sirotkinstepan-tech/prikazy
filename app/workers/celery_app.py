from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ocr_document_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)
celery_app.conf.task_default_queue = "ocr"
celery_app.conf.task_routes = {"app.workers.tasks.*": {"queue": "ocr"}}
