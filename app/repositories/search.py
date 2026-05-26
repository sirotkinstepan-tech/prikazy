from datetime import date, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class SearchRepository:
    def __init__(self, session: Session):
        self.session = session

    def search(
        self,
        *,
        tenant_id: UUID,
        query: str,
        doc_type: str | None = None,
        status: str | None = None,
        document_date_from: date | None = None,
        document_date_to: date | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
        counterparty_name: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        filters = ["d.tenant_id = :tenant_id", "lor.search_vector @@ q.tsq"]
        params = {
            "tenant_id": tenant_id,
            "query": query,
            "limit": limit,
            "offset": offset,
        }
        if doc_type:
            filters.append("d.doc_type = :doc_type")
            params["doc_type"] = doc_type
        if status:
            filters.append("d.status = :status")
            params["status"] = status
        if document_date_from:
            filters.append("d.document_date >= :document_date_from")
            params["document_date_from"] = document_date_from
        if document_date_to:
            filters.append("d.document_date <= :document_date_to")
            params["document_date_to"] = document_date_to
        if created_at_from:
            filters.append("d.created_at >= :created_at_from")
            params["created_at_from"] = created_at_from
        if created_at_to:
            filters.append("d.created_at <= :created_at_to")
            params["created_at_to"] = created_at_to
        if counterparty_name:
            filters.append("d.counterparty_name ILIKE :counterparty_name")
            params["counterparty_name"] = f"%{counterparty_name}%"

        where_clause = " AND ".join(filters)
        base_cte = """
            WITH q AS (
                SELECT websearch_to_tsquery('simple', :query) AS tsq
            ),
            latest_ocr AS (
                SELECT DISTINCT ON (document_id, document_created_at)
                    id,
                    processed_at,
                    document_id,
                    document_created_at,
                    full_text,
                    search_vector
                FROM ocr_results
                ORDER BY document_id, document_created_at, processed_at DESC
            )
        """
        count_sql = text(
            f"""
            {base_cte}
            SELECT count(*) AS total
            FROM documents d
            JOIN latest_ocr lor
              ON lor.document_id = d.id
             AND lor.document_created_at = d.created_at
            CROSS JOIN q
            WHERE {where_clause}
            """
        )
        items_sql = text(
            f"""
            {base_cte}
            SELECT
                d.id AS document_id,
                d.status,
                d.doc_type,
                d.document_date,
                d.counterparty_name,
                ts_rank(lor.search_vector, q.tsq) AS rank,
                ts_headline('simple', lor.full_text, q.tsq) AS snippet
            FROM documents d
            JOIN latest_ocr lor
              ON lor.document_id = d.id
             AND lor.document_created_at = d.created_at
            CROSS JOIN q
            WHERE {where_clause}
            ORDER BY rank DESC, d.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        )
        total = self.session.execute(count_sql, params).scalar_one()
        rows = self.session.execute(items_sql, params).mappings().all()
        return [dict(row) for row in rows], int(total)
