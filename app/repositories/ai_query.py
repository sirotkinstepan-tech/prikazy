from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

GROUP_BY_COLUMNS = {
    "doc_type": "d.doc_type",
    "status": "d.status",
    "counterparty_name": "d.counterparty_name",
    "document_date_month": "date_trunc('month', d.document_date)::date",
}

LATEST_OCR_CTE = """
    latest_ocr AS (
        SELECT DISTINCT ON (document_id, document_created_at)
            id,
            processed_at,
            document_id,
            document_created_at
        FROM ocr_results
        ORDER BY document_id, document_created_at, processed_at DESC
    )
"""


class AiQueryRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_by_extracted_field(
        self,
        *,
        tenant_id: UUID,
        field_name: str | None = None,
        field_value: str | None = None,
        doc_type: str | None = None,
        doc_types: list[str] | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        filters = ["d.tenant_id = :tenant_id"]
        params: dict = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
        }
        if field_name:
            filters.append("ef.field_name ILIKE :field_name")
            params["field_name"] = f"%{field_name}%"
        if field_value:
            filters.append("ef.field_value ILIKE :field_value")
            params["field_value"] = f"%{field_value}%"
        if doc_types:
            filters.append("d.doc_type = ANY(:doc_types)")
            params["doc_types"] = doc_types
        elif doc_type:
            filters.append("d.doc_type = :doc_type")
            params["doc_type"] = doc_type
        if status:
            filters.append("d.status = :status")
            params["status"] = status

        where_clause = " AND ".join(filters)
        base_cte = f"WITH {LATEST_OCR_CTE}"
        count_sql = text(
            f"""
            {base_cte}
            SELECT count(DISTINCT (d.id, d.created_at)) AS total
            FROM documents d
            JOIN latest_ocr lor
              ON lor.document_id = d.id
             AND lor.document_created_at = d.created_at
            JOIN extracted_fields ef
              ON ef.document_id = d.id
             AND ef.document_created_at = d.created_at
             AND ef.ocr_result_id = lor.id
             AND ef.ocr_result_processed_at = lor.processed_at
            WHERE {where_clause}
            """
        )
        items_sql = text(
            f"""
            {base_cte}
            SELECT DISTINCT ON (d.id, d.created_at)
                d.id AS document_id,
                d.created_at,
                d.status,
                d.doc_type,
                d.document_date,
                d.counterparty_name,
                d.title,
                ef.field_name,
                ef.field_value
            FROM documents d
            JOIN latest_ocr lor
              ON lor.document_id = d.id
             AND lor.document_created_at = d.created_at
            JOIN extracted_fields ef
              ON ef.document_id = d.id
             AND ef.document_created_at = d.created_at
             AND ef.ocr_result_id = lor.id
             AND ef.ocr_result_processed_at = lor.processed_at
            WHERE {where_clause}
            ORDER BY d.id, d.created_at, ef.field_name
            LIMIT :limit OFFSET :offset
            """
        )
        total = self.session.execute(count_sql, params).scalar_one()
        rows = self.session.execute(items_sql, params).mappings().all()
        return [dict(row) for row in rows], int(total)

    def group_documents(
        self,
        *,
        tenant_id: UUID,
        group_by: str,
        doc_type: str | None = None,
        doc_types: list[str] | None = None,
        status: str | None = None,
        document_date_from: date | None = None,
        document_date_to: date | None = None,
        limit: int = 50,
    ) -> list[dict]:
        group_expr = GROUP_BY_COLUMNS.get(group_by)
        if group_expr is None:
            raise ValueError(f"Unsupported group_by: {group_by}")

        filters = ["d.tenant_id = :tenant_id", "d.archived_at IS NULL"]
        params: dict = {"tenant_id": tenant_id, "limit": limit}
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

        where_clause = " AND ".join(filters)
        sql = text(
            f"""
            SELECT
                {group_expr} AS group_key,
                count(*) AS document_count
            FROM documents d
            WHERE {where_clause}
            GROUP BY group_key
            ORDER BY document_count DESC, group_key NULLS LAST
            LIMIT :limit
            """
        )
        rows = self.session.execute(sql, params).mappings().all()
        return [dict(row) for row in rows]

    def list_distinct_field_names(
        self,
        *,
        tenant_id: UUID,
        name_pattern: str | None = None,
        doc_types: list[str] | None = None,
        limit: int = 100,
    ) -> list[str]:
        filters = ["d.tenant_id = :tenant_id"]
        params: dict = {"tenant_id": tenant_id, "limit": limit}
        if doc_types:
            filters.append("d.doc_type = ANY(:doc_types)")
            params["doc_types"] = doc_types
        if name_pattern:
            filters.append("ef.field_name ILIKE :name_pattern")
            params["name_pattern"] = f"%{name_pattern}%"

        where_clause = " AND ".join(filters)
        sql = text(
            f"""
            WITH {LATEST_OCR_CTE}
            SELECT DISTINCT ef.field_name
            FROM documents d
            JOIN latest_ocr lor
              ON lor.document_id = d.id
             AND lor.document_created_at = d.created_at
            JOIN extracted_fields ef
              ON ef.document_id = d.id
             AND ef.document_created_at = d.created_at
             AND ef.ocr_result_id = lor.id
             AND ef.ocr_result_processed_at = lor.processed_at
            WHERE {where_clause}
            ORDER BY ef.field_name
            LIMIT :limit
            """
        )
        rows = self.session.execute(sql, params).scalars().all()
        return list(rows)
