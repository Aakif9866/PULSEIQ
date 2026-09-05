"""Application configuration.

All configuration is sourced from environment variables (see .env.example at
the repo root). Nothing here should ever contain a real secret — defaults are
safe-for-local-dev placeholders only.
"""
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET_KEY = "insecure-dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "PulseIQ"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # --- Security ---
    SECRET_KEY: str = Field(
        default=_INSECURE_DEFAULT_SECRET_KEY,
        description="Used to sign JWTs. Must be overridden in every non-local environment.",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14  # 14d

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg://pulseiq:pulseiq@localhost:5432/pulseiq"

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        """Managed Postgres providers (Neon, Supabase, RDS, ...) hand out
        driver-less `postgresql://` URLs, which SQLAlchemy resolves to the
        legacy psycopg2 dialect — but this project only installs psycopg
        (v3). Rewrite so any standard connection string works as pasted,
        without requiring a manual scheme edit."""
        for bare_scheme in ("postgresql://", "postgres://"):
            if value.startswith(bare_scheme):
                return "postgresql+psycopg://" + value[len(bare_scheme) :]
        return value

    # --- Storage (phase 2) ---
    STORAGE_PROVIDER: Literal["local", "r2"] = "local"
    LOCAL_STORAGE_ROOT: str = "./data/uploads"

    R2_ACCOUNT_ID: str | None = None
    R2_ACCESS_KEY_ID: str | None = None
    R2_SECRET_ACCESS_KEY: str | None = None
    R2_BUCKET_NAME: str | None = None
    R2_ENDPOINT_URL: str | None = None

    MAX_UPLOAD_SIZE_MB: int = 200
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = [".csv", ".xlsx", ".xls"]

    # Reserved for a future scheduled cleanup job (needs the background
    # worker infra deferred in Phase 6 — no such job runs yet). Defaults to
    # off so defining these has no effect until something actually reads
    # them; see docs/STORAGE.md.
    ENABLE_STORAGE_CLEANUP: bool = False
    DATASET_RETENTION_DAYS: int = 7

    # --- AI (phase 4) ---
    AI_PROVIDER: Literal["groq", "none"] = "none"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    AI_REQUEST_TIMEOUT_SECONDS: int = 30

    # --- Analytics query safety (phase 3/4) ---
    QUERY_TIMEOUT_SECONDS: int = 10
    QUERY_ROW_LIMIT: int = 10_000

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> Self:
        """Refuse to boot with dev-only defaults in production — a
        misconfigured deploy should fail loudly at startup, not silently
        sign tokens with a secret anyone can read in this repo."""
        if self.ENVIRONMENT != "production":
            return self

        if self.SECRET_KEY == _INSECURE_DEFAULT_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY is still the insecure default. Set a real, unique "
                "SECRET_KEY before running with ENVIRONMENT=production."
            )
        if self.DEBUG:
            raise ValueError("DEBUG must be false when ENVIRONMENT=production.")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
