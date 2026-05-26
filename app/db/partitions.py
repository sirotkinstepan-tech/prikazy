from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

PARTITIONED_TABLES = {
    "documents": "created_at",
    "ocr_results": "processed_at",
}


@dataclass(frozen=True)
class MonthlyPartition:
    table_name: str
    partition_name: str
    start: date
    end: date


def month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def build_monthly_partition(table_name: str, start: date) -> MonthlyPartition:
    if table_name not in PARTITIONED_TABLES:
        raise ValueError(f"Unsupported partitioned table: {table_name}")

    normalized_start = month_start(start)
    return MonthlyPartition(
        table_name=table_name,
        partition_name=f"{table_name}_{normalized_start:%Y_%m}",
        start=normalized_start,
        end=add_months(normalized_start, 1),
    )


def render_create_partition_sql(partition: MonthlyPartition) -> str:
    return (
        f"CREATE TABLE IF NOT EXISTS {partition.partition_name} "
        f"PARTITION OF {partition.table_name} "
        f"FOR VALUES FROM ('{partition.start.isoformat()}') "
        f"TO ('{partition.end.isoformat()}')"
    )


def create_monthly_partition(session: Session, table_name: str, start: date) -> MonthlyPartition:
    partition = build_monthly_partition(table_name, start)
    session.execute(text(render_create_partition_sql(partition)))
    return partition


def ensure_future_partitions(
    session: Session,
    *,
    from_date: date | None = None,
    months_ahead: int = 3,
) -> list[MonthlyPartition]:
    if months_ahead < 0:
        raise ValueError("months_ahead must be non-negative")

    start = month_start(from_date or date.today())
    created: list[MonthlyPartition] = []
    for offset in range(months_ahead + 1):
        partition_start = add_months(start, offset)
        for table_name in PARTITIONED_TABLES:
            created.append(create_monthly_partition(session, table_name, partition_start))
    return created
