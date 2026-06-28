"""
Talentick — Application Configuration
======================================
تمام تنظیمات از environment variables خوانده می‌شود.
Pydantic Settings اعتبارسنجی خودکار انجام می‌دهد.

استفاده:
    from app.config import settings
    print(settings.database_url)
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """تنظیمات اصلی برنامه — از .env فایل خوانده می‌شود."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── App ─────────────────────────────────────────────────────────────
    app_name: str = "Talentick"
    app_env: Literal["development", "production", "test"] = "development"
    debug: bool = False
    secret_key: str                         # اجباری — بدون مقدار پیش‌فرض

    # لیست origin های مجاز برای CORS — با کاما جدا می‌شوند
    allowed_origins: list[str] = ["http://localhost", "http://localhost:80"]

    # ─── Database ─────────────────────────────────────────────────────────
    database_url: str                       # اجباری
    # تعداد connection های pool
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ─── JWT ──────────────────────────────────────────────────────────────
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ─── MinIO ────────────────────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin123"
    minio_bucket_name: str = "talentick"
    minio_use_ssl: bool = False

    # ─── Organization (V0 single-tenant) ──────────────────────────────────
    default_org_slug: str = "my-company"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list) -> list[str]:
        """از string کاما-جدا یا list می‌پذیرد."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Settings را یک بار می‌سازد و cache می‌کند.
    لازم نیست هر بار از disk بخواند.
    """
    return Settings()


# ─── Singleton برای استفاده در سراسر برنامه ─────────────────────────────
settings = get_settings()