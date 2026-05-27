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

    database_url: str = Field(
        default="postgresql+psycopg://prikazy:prikazy@localhost:5433/prikazy",
        validation_alias="DATABASE_URL",
    )
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    s3_endpoint_url: str = "http://localhost:9000"
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

    llm_provider: str = Field(default="yandex", validation_alias="LLM_PROVIDER")
    llm_api_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="LLM_API_BASE_URL",
    )
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")
    llm_timeout_seconds: float = Field(default=60.0, validation_alias="LLM_TIMEOUT_SECONDS")
    llm_max_tool_rounds: int = Field(default=5, validation_alias="LLM_MAX_TOOL_ROUNDS")
    llm_max_output_tokens: int = Field(default=2000, validation_alias="LLM_MAX_OUTPUT_TOKENS")

    yandex_api_key: str = Field(default="", validation_alias="YANDEX_API_KEY")
    yandex_folder_id: str = Field(default="", validation_alias="YANDEX_FOLDER_ID")
    yandex_model: str = Field(
        default="yandexgpt-lite/latest",
        validation_alias="YANDEX_MODEL",
    )

    auth_required_for_ai: bool = Field(default=True, validation_alias="AUTH_REQUIRED_FOR_AI")

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
