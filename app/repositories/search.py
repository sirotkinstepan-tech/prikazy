import re
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

MIN_SEARCH_TOKEN_LEN = 3
STEM_MIN_LEN = 5


def tokenize_search_query(query: str) -> list[str]:
    tokens = re.findall(r"[^\W_]+", query, flags=re.UNICODE)
    seen: set[str] = set()
    normalized: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if len(lowered) < MIN_SEARCH_TOKEN_LEN or lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(lowered)
    return normalized


def token_like_pattern(token: str) -> str:
    if len(token) >= STEM_MIN_LEN:
        return f"%{token[:-1]}%"
    return f"%{token}%"


def _build_text_match_clause(tokens: list[str], params: dict) -> str:
    if not tokens:
        return """(
                d.title ILIKE :like_pattern
                OR d.source_filename ILIKE :like_pattern
                OR lor.full_text ILIKE :like_pattern
                OR (lor.search_vector IS NOT NULL AND lor.search_vector @@ q.tsq)
            )"""

    token_clauses: list[str] = []
    for index, token in enumerate(tokens):
        param_name = f"token_{index}"
        params[param_name] = token_like_pattern(token)
        token_clauses.append(
            f"""(
                d.title ILIKE :{param_name}
                OR d.source_filename ILIKE :{param_name}
                OR lor.full_text ILIKE :{param_name}
            )"""
        )

    token_match = " AND ".join(token_clauses)
    return f"""(
                ({token_match})
                OR d.title ILIKE :like_pattern
                OR d.source_filename ILIKE :like_pattern
                OR lor.full_text ILIKE :like_pattern
                OR (lor.search_vector IS NOT NULL AND lor.search_vector @@ q.tsq)
            )"""


def _title_token_match_expr(tokens: list[str]) -> str:
    if not tokens:
        return "FALSE"
    return " OR ".join(f"d.title ILIKE :token_{index}" for index in range(len(tokens)))


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
        active_only: bool = True,
        include_trashed: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        query = query.strip()
        tokens = tokenize_search_query(query)
        like_pattern = f"%{query}%"
        params: dict = {
            "tenant_id": tenant_id,
            "query": query,
            "like_pattern": like_pattern,
            "limit": limit,
            "offset": offset,
        }
        text_match_clause = _build_text_match_clause(tokens, params)
        title_token_match = _title_token_match_expr(tokens)
        filters = [
            "d.tenant_id = :tenant_id",
            text_match_clause,
        ]
        if active_only:
            filters.append("d.archived_at IS NULL")
        elif include_trashed:
            filters.append("d.archived_at IS NOT NULL")
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
        select_fields = f"""
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
                    WHEN {title_token_match} THEN 0.9
                    ELSE COALESCE(ts_rank(lor.search_vector, q.tsq), 0)
                END AS rank,
                CASE
                    WHEN d.title ILIKE :like_pattern THEN d.title
                    WHEN {title_token_match} THEN d.title
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
