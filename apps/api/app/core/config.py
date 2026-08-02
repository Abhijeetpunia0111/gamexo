"""Application configuration, sourced entirely from the environment."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
PoolMode = Literal["direct", "external_pooler"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Environment = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    project_name: str = "gamexo API"

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str
    migration_database_url: str
    db_app_user: str = "gamexo_app"
    db_pool_mode: PoolMode = "direct"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_echo: bool = False

    # ── Tenancy ─────────────────────────────────────────────────────────────
    tenant_base_domain: str = "gamexo.app"
    allow_tenant_header: bool = False

    # ── Auth ────────────────────────────────────────────────────────────────
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14

    # ── HTTP ────────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=list)

    # ── Seed ────────────────────────────────────────────────────────────────
    seed_tenant_slug: str = "xcourt"
    seed_tenant_name: str = "XCourt Sports"
    seed_admin_email: str = "admin@xcourtsports.com"
    seed_admin_password: str = "xcourt-admin-dev"
    seed_platform_admin_email: str = "ops@gamexo.app"
    seed_platform_admin_password: str = "gamexo-platform-dev"

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _require_asyncpg_driver(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "must use the asyncpg driver, e.g. postgresql+asyncpg://user:pw@host/db"
            )
        return v

    @model_validator(mode="after")
    def _guard_production(self) -> Settings:
        if self.environment != "production":
            return self

        # X-Tenant-ID lets the caller name any tenant they like. That is exactly
        # what you want for curl and pytest, and a total isolation bypass in
        # production. Refuse to boot rather than serve with it on.
        if self.allow_tenant_header:
            raise ValueError(
                "ALLOW_TENANT_HEADER must be false in production: the header lets any "
                "caller select any tenant, bypassing host-based resolution entirely."
            )

        # The app and migrator URLs pointing at the same role means the API is
        # connecting as the table owner, which silently exempts it from RLS.
        if self.database_url == self.migration_database_url:
            raise ValueError(
                "DATABASE_URL must not equal MIGRATION_DATABASE_URL: the API must connect "
                "as a non-owner role, or RLS policies do not apply to it."
            )

        if len(self.jwt_secret_key.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")

        return self

    @property
    def is_testing(self) -> bool:
        return self.environment == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment


settings = get_settings()
