from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="app.workers.tasks.process_ocr_job", bind=True)
def process_ocr_job(self, job_id: str) -> dict[str, str]:
    from app.core.errors import ApplicationError
    from app.services.ocr_service import OcrProcessingService

    try:
        service = OcrProcessingService()
        service.process_job(job_id)
    except (ApplicationError, ValueError):
        raise
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries, max_retries=3) from exc
    return {"job_id": job_id, "status": "processed"}
