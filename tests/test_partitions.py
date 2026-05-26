from datetime import date

from app.db.partitions import (
    build_monthly_partition,
    ensure_future_partitions,
    render_create_partition_sql,
)


class FakeSession:
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))


def test_build_monthly_partition_normalizes_start_date():
    partition = build_monthly_partition("documents", date(2026, 5, 14))

    assert partition.partition_name == "documents_2026_05"
    assert partition.start == date(2026, 5, 1)
    assert partition.end == date(2026, 6, 1)


def test_render_create_partition_sql():
    partition = build_monthly_partition("ocr_results", date(2026, 12, 3))

    sql = render_create_partition_sql(partition)

    assert "CREATE TABLE IF NOT EXISTS ocr_results_2026_12" in sql
    assert "PARTITION OF ocr_results" in sql
    assert "FROM ('2026-12-01')" in sql
    assert "TO ('2027-01-01')" in sql


def test_ensure_future_partitions_creates_both_tables():
    session = FakeSession()

    created = ensure_future_partitions(session, from_date=date(2026, 5, 14), months_ahead=1)

    assert [partition.partition_name for partition in created] == [
        "documents_2026_05",
        "ocr_results_2026_05",
        "documents_2026_06",
        "ocr_results_2026_06",
    ]
    assert len(session.statements) == 4
