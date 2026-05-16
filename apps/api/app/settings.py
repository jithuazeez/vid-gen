from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://vidplatform:dev@localhost:5432/vidplatform"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str | None = None
    s3_bucket: str = "vidplatform"
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    gemini_api_key: str = ""
    sarvam_api_key: str = ""

    modal_token_id: str = ""
    modal_token_secret: str = ""
    modal_app_name: str = "vidplatform"

    modal_global_cost_cap_usd: float = Field(default=25.0, ge=0)
    modal_per_project_cost_cap_usd: float = Field(default=1.5, ge=0)

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
