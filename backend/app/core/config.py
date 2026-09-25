"""Application configuration.

All configuration is sourced from environment variables (see .env.example at
the repo root). Nothing here should ever contain a real secret — defaults are
safe-for-local-dev placeholders only.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET_KEY = "insecure-dev-secret-change-me"

# pydantic-settings resolves a relative env_file against the process's
# *current working directory*, not this file's location — a plain ".env"
# here silently found nothing (and fell back to every class default, with
# no warning) whenever the app/alembic/pytest was launched from backend/
# instead of the repo root, which is exactly the workflow README.md itself
# documents ("cd backend && uvicorn ...", "cd backend && pytest"). Anchoring
# to this file's real location makes the repo-root .env get found
# regardless of the caller's cwd.
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
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
    # USD per 1,000,000 tokens, for the model above — deliberately no
    # default. Groq's current pricing (their pricing page renders
    # client-side; wasn't fetchable to hardcode a verified number here)
    # changes and varies by model, so cost is only ever computed when an
    # operator sets both of these from Groq's own current numbers; left
    # unset, cost is honestly reported as unavailable rather than an
    # invented figure. See app/ai/providers/usage_tracking.py.
    GROQ_INPUT_COST_PER_1M_TOKENS: float | None = None
    GROQ_OUTPUT_COST_PER_1M_TOKENS: float | None = None
    # Per-user token budget per UTC calendar day, across AI requests.
    # None (the default) = no quota enforced, only usage recorded — opt-in,
    # so an existing deployment's behavior doesn't change underneath it.
    AI_DAILY_TOKEN_QUOTA_PER_USER: int | None = None

    # --- Optional tracing (Phase 8 step 5) — see app/core/tracing.py ---
    # Standard OpenTelemetry variable names, but read through Settings on
    # purpose: pydantic-settings loads .env into Settings, NOT into
    # os.environ, so the OTLP exporter reading os.environ itself would
    # silently never see an endpoint configured in .env. Unset = tracing
    # off entirely (a no-op tracer, nothing exported).
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    # "key1=value1,key2=value2" — e.g. an API-key header for a hosted
    # backend. Never logged.
    OTEL_EXPORTER_OTLP_HEADERS: str | None = None
    OTEL_SERVICE_NAME: str = "pulseiq-backend"

    # --- Public demo account (Phase 8 step 6) — see app/workers/seed_demo.py ---
    # Both unset = no demo account is created (the default everywhere
    # except a deliberately public deployment). When set, the seeder runs
    # at container start and (re)creates the account, a sample dataset,
    # and a dashboard — idempotently, repairing anything a visitor
    # deleted or a redeploy wiped.
    DEMO_USER_EMAIL: str | None = None
    DEMO_USER_PASSWORD: str | None = None

    # --- Analytics query safety (phase 3/4) ---
    QUERY_TIMEOUT_SECONDS: int = 10
    QUERY_ROW_LIMIT: int = 10_000

    # --- Anomaly monitoring / alerting (V2) ---
    # Email is sent via stdlib smtplib — no new dependency. Unset SMTP_HOST
    # (the default) means email alerting is simply disabled: an anomaly is
    # still detected and persisted, only the email step is skipped, with
    # that recorded on the anomaly rather than treated as a hard failure.
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_USE_TLS: bool = True

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
