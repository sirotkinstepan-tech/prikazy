"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE storage_objects (
            id uuid PRIMARY KEY,
            bucket text NOT NULL,
            object_key text NOT NULL,
            version_id text NULL,
            sha256 text NOT NULL,
            size_bytes bigint NOT NULL,
            mime_type text NOT NULL,
            original_filename text NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE UNIQUE INDEX uq_storage_objects_location
            ON storage_objects (bucket, object_key, coalesce(version_id, ''));
        CREATE INDEX ix_storage_objects_sha256 ON storage_objects (sha256);

        CREATE TABLE documents (
            id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            tenant_id uuid NOT NULL,
            storage_object_id uuid NOT NULL REFERENCES storage_objects(id),
            status text NOT NULL,
            doc_type text NULL,
            document_date date NULL,
            counterparty_name text NULL,
            title text NULL,
            source_filename text NULL,
            mime_type text NOT NULL,
            size_bytes bigint NOT NULL,
            sha256 text NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            archived_at timestamptz NULL,
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);

        CREATE INDEX ix_documents_tenant_created_at ON documents (tenant_id, created_at DESC);
        CREATE INDEX ix_documents_tenant_status ON documents (tenant_id, status);
        CREATE INDEX ix_documents_tenant_doc_type ON documents (tenant_id, doc_type);
        CREATE INDEX ix_documents_tenant_document_date ON documents (tenant_id, document_date);
        CREATE INDEX ix_documents_tenant_counterparty ON documents (tenant_id, counterparty_name);
        CREATE INDEX ix_documents_sha256 ON documents (sha256);

        CREATE TABLE document_pages (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL,
            document_created_at timestamptz NOT NULL,
            page_number integer NOT NULL,
            storage_object_id uuid NULL REFERENCES storage_objects(id),
            width integer NULL,
            height integer NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_document_pages_documents
                FOREIGN KEY (document_id, document_created_at)
                REFERENCES documents(id, created_at),
            CONSTRAINT uq_document_pages_document_page
                UNIQUE (document_id, document_created_at, page_number)
        );

        CREATE TABLE processing_jobs (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL,
            document_created_at timestamptz NOT NULL,
            job_type text NOT NULL,
            status text NOT NULL,
            attempt integer NOT NULL DEFAULT 0,
            max_attempts integer NOT NULL DEFAULT 3,
            celery_task_id text NULL,
            error_code text NULL,
            error_message text NULL,
            locked_at timestamptz NULL,
            started_at timestamptz NULL,
            finished_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_processing_jobs_documents
                FOREIGN KEY (document_id, document_created_at)
                REFERENCES documents(id, created_at)
        );

        CREATE INDEX ix_processing_jobs_status_created_at
            ON processing_jobs (status, created_at);
        CREATE INDEX ix_processing_jobs_document
            ON processing_jobs (document_id, document_created_at);
        CREATE INDEX ix_processing_jobs_celery_task_id
            ON processing_jobs (celery_task_id);
        CREATE INDEX ix_processing_jobs_type_status
            ON processing_jobs (job_type, status);

        CREATE TABLE ocr_results (
            id uuid NOT NULL,
            processed_at timestamptz NOT NULL DEFAULT now(),
            document_id uuid NOT NULL,
            document_created_at timestamptz NOT NULL,
            job_id uuid NOT NULL REFERENCES processing_jobs(id),
            provider text NOT NULL,
            language text NULL,
            full_text text NOT NULL,
            confidence numeric(5, 4) NULL,
            layout_json jsonb NULL,
            page_data jsonb NULL,
            search_vector tsvector GENERATED ALWAYS AS
                (to_tsvector('simple', coalesce(full_text, ''))) STORED,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (id, processed_at),
            CONSTRAINT fk_ocr_results_documents
                FOREIGN KEY (document_id, document_created_at)
                REFERENCES documents(id, created_at)
        ) PARTITION BY RANGE (processed_at);

        CREATE INDEX ix_ocr_results_search_vector ON ocr_results USING gin (search_vector);
        CREATE INDEX ix_ocr_results_layout_json ON ocr_results USING gin (layout_json);
        CREATE INDEX ix_ocr_results_document_processed_at
            ON ocr_results (document_id, document_created_at, processed_at DESC);
        CREATE INDEX ix_ocr_results_job_id ON ocr_results (job_id);

        CREATE TABLE extracted_fields (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL,
            document_created_at timestamptz NOT NULL,
            ocr_result_id uuid NOT NULL,
            ocr_result_processed_at timestamptz NOT NULL,
            field_name text NOT NULL,
            field_value text NOT NULL,
            field_type text NULL,
            confidence numeric(5, 4) NULL,
            source_json jsonb NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_extracted_fields_documents
                FOREIGN KEY (document_id, document_created_at)
                REFERENCES documents(id, created_at),
            CONSTRAINT fk_extracted_fields_ocr_results
                FOREIGN KEY (ocr_result_id, ocr_result_processed_at)
                REFERENCES ocr_results(id, processed_at)
        );

        CREATE INDEX ix_extracted_fields_document
            ON extracted_fields (document_id, document_created_at);
        CREATE INDEX ix_extracted_fields_name_value
            ON extracted_fields (field_name, field_value);

        CREATE TABLE processing_events (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL,
            document_created_at timestamptz NOT NULL,
            job_id uuid NULL REFERENCES processing_jobs(id),
            event_type text NOT NULL,
            message text NULL,
            payload jsonb NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_processing_events_documents
                FOREIGN KEY (document_id, document_created_at)
                REFERENCES documents(id, created_at)
        );

        CREATE INDEX ix_processing_events_document_created_at
            ON processing_events (document_id, document_created_at, created_at);
        CREATE INDEX ix_processing_events_job_created_at
            ON processing_events (job_id, created_at);
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            month_start date := date_trunc('month', now())::date;
            partition_start date;
            partition_end date;
            suffix text;
        BEGIN
            FOR i IN 0..2 LOOP
                partition_start := month_start + (i || ' months')::interval;
                partition_end := partition_start + interval '1 month';
                suffix := to_char(partition_start, 'YYYY_MM');

                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS documents_%s PARTITION OF documents
                     FOR VALUES FROM (%L) TO (%L)',
                    suffix,
                    partition_start,
                    partition_end
                );

                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS ocr_results_%s PARTITION OF ocr_results
                     FOR VALUES FROM (%L) TO (%L)',
                    suffix,
                    partition_start,
                    partition_end
                );
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS processing_events CASCADE;
        DROP TABLE IF EXISTS extracted_fields CASCADE;
        DROP TABLE IF EXISTS ocr_results CASCADE;
        DROP TABLE IF EXISTS processing_jobs CASCADE;
        DROP TABLE IF EXISTS document_pages CASCADE;
        DROP TABLE IF EXISTS documents CASCADE;
        DROP TABLE IF EXISTS storage_objects CASCADE;
        """
    )
