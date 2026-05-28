#!/usr/bin/env python3
"""Requeue OCR jobs for documents previously processed with stub OCR."""

from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.document import Document
from app.models.ocr_result import OcrResult
from app.services.job_service import JobService
from app.workers.tasks import process_ocr_job


def _latest_providers(session, tenant_id=None) -> list[tuple[Document, str | None]]:
    rows = session.execute(
        select(Document, OcrResult.provider)
        .join(
            OcrResult,
            (OcrResult.document_id == Document.id)
            & (OcrResult.document_created_at == Document.created_at),
        )
        .where(Document.archived_at.is_(None))
        .order_by(Document.created_at.desc(), OcrResult.processed_at.desc())
    ).all()
    seen: set[tuple] = set()
    result: list[tuple[Document, str | None]] = []
    for document, provider in rows:
        key = (document.id, document.created_at)
        if key in seen:
            continue
        seen.add(key)
        if tenant_id is not None and str(document.tenant_id) != tenant_id:
            continue
        result.append((document, provider))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        default="stub",
        help="Reprocess documents whose latest OCR used this provider (default: stub)",
    )
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="Optional tenant UUID filter",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Reprocess all active documents regardless of provider",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        candidates = _latest_providers(session, tenant_id=args.tenant_id)
        targets: list[tuple] = []
        for document, provider in candidates:
            if args.all or provider == args.provider:
                targets.append(
                    (
                        document.id,
                        document.tenant_id,
                        document.title or document.source_filename,
                        provider,
                    )
                )

        if not targets:
            print("No documents matched.")
            return

        for document_id, tenant_id, label, provider in targets:
            with SessionLocal() as session:
                service = JobService(session)
                job, _ = service.create_reprocess_job(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    reason=f"Reprocess after switching OCR provider (was: {provider})",
                    enqueue_ocr_job=process_ocr_job.delay,
                )
                print(f"queued {document_id} ({label}) -> job {job.id}")


if __name__ == "__main__":
    main()
