from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "prikazy"
    app_env: str = "local"
    app_debug: bool = False
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    public_api_base_url: str = Field(
        default="http://localhost:8001",
        validation_alias="PUBLIC_API_BASE_URL",
    )
    default_tenant_id: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        validation_alias="DEFAULT_TENANT_ID",
    )

    database_url: str = Field(
        default="postgresql+psycopg://prikazy:prikazy@localhost:5433/prikazy",
        validation_alias="DATABASE_URL",
    )
    celery_broker_url: str = "redis://localhost:6380/0"
    celery_result_backend: str = "redis://localhost:6380/1"

    s3_endpoint_url: str = "http://localhost:9002"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "documents"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = False

    max_upload_size_bytes: int = 50 * 1024 * 1024
    allowed_mime_types: str = (
        "application/pdf,image/png,image/jpeg,image/tiff,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    default_ocr_provider: str = "stub"

    session_secret: str = Field(
        default="change-me-in-production-use-a-long-random-string",
        validation_alias="SESSION_SECRET",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_mime_type_set(self) -> set[str]:
        return {item.strip() for item in self.allowed_mime_types.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
