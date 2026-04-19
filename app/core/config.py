from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared import normalize_postgres_async_url


class Settings(BaseSettings):
    service_name: str = "foresightx-auth"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8004

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/foresightx_auth"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    session_secret: str | None = None

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: AnyHttpUrl | None = None

    profile_service_url: str = "http://foresightx-profile"
    profile_create_path: str = "/profiles"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"])
    request_timeout_seconds: float = 10.0
    http_max_retries: int = 2

    rate_limit_enabled: bool = False
    rate_limit_requests: int = 5
    rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        enable_decoding=False,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        return normalize_postgres_async_url(value)

    @model_validator(mode="after")
    def ensure_session_secret(self) -> "Settings":
        if not self.session_secret:
            self.session_secret = self.jwt_secret
        return self

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
