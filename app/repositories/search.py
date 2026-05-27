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
        doc_types: list[str] | None = None,
        status: str | None = None,
        document_date_from: date | None = None,
        document_date_to: date | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
        counterparty_name: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        query = query.strip()
        like_pattern = f"%{query}%"
        filters = [
            "d.tenant_id = :tenant_id",
            """(
                d.title ILIKE :like_pattern
                OR d.source_filename ILIKE :like_pattern
                OR lor.full_text ILIKE :like_pattern
                OR (lor.search_vector IS NOT NULL AND lor.search_vector @@ q.tsq)
            )""",
        ]
        params: dict = {
            "tenant_id": tenant_id,
            "query": query,
            "like_pattern": like_pattern,
            "limit": limit,
            "offset": offset,
        }
        if doc_types:
            filters.append("d.doc_type = ANY(:doc_types)")
            params["doc_types"] = doc_types
        elif doc_type:
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
        select_fields = """
            SELECT
                d.id AS document_id,
                d.title,
                d.source_filename,
                d.status,
                d.doc_type,
                d.document_date,
                d.counterparty_name,
                CASE
                    WHEN d.title ILIKE :like_pattern
                         OR d.source_filename ILIKE :like_pattern THEN 1.0
                    ELSE COALESCE(ts_rank(lor.search_vector, q.tsq), 0)
                END AS rank,
                CASE
                    WHEN d.title ILIKE :like_pattern THEN d.title
                    WHEN d.source_filename ILIKE :like_pattern THEN d.source_filename
                    ELSE ts_headline('simple', lor.full_text, q.tsq)
                END AS snippet
        """
        from_clause = """
            FROM documents d
            LEFT JOIN latest_ocr lor
              ON lor.document_id = d.id
             AND lor.document_created_at = d.created_at
            CROSS JOIN q
        """
        count_sql = text(
            f"""
            {base_cte}
            SELECT count(*) AS total
            {from_clause}
            WHERE {where_clause}
            """
        )
        items_sql = text(
            f"""
            {base_cte}
            {select_fields}
            {from_clause}
            WHERE {where_clause}
            ORDER BY rank DESC, d.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        )
        total = self.session.execute(count_sql, params).scalar_one()
        rows = self.session.execute(items_sql, params).mappings().all()
        return [dict(row) for row in rows], int(total)
