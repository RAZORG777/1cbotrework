"""Настройки Telegram-бота. Все секреты — только из .env (конституция, принцип I)."""

from __future__ import annotations

import sys
from functools import cached_property
from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


def _https(value: str) -> str:
    if not value.startswith("https://"):
        raise ValueError("должен начинаться с https://")
    return value.rstrip("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    BOT_TOKEN: str = Field(min_length=1)
    TELEGRAM_API_BASE: str = "https://api.telegram.org"
    TG_WEBHOOK_SECRET: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")
    ADMIN_IDS: str = ""

    # WebApp
    WEBAPP_URL: str
    WEBAPP_URL2: str = "https://yasno-vizhu.com"
    PD_POLICY_URL: str
    INIT_DATA_MAX_AGE_HOURS: int = Field(24, ge=1)

    # 1С
    ONEC_URL: str = Field(min_length=1)
    ONEC_USER: str = Field(min_length=1)
    ONEC_PASSWORD: str = Field(min_length=1)
    ONEC_WEBHOOK_SECRET: str = Field(min_length=1)

    # Админка
    ADMIN_USERNAME: str = Field("admin", min_length=1)
    ADMIN_PASSWORD: str = Field(min_length=1)

    # Хранение и служебное
    PD_RETENTION_DAYS: int = Field(30, ge=1)
    DB_PATH: str = "appointments.db"
    LOG_DIR: str = "logs"
    HOST: str = "127.0.0.1"
    PORT: int = 8001

    _check_https = field_validator(
        "TELEGRAM_API_BASE", "WEBAPP_URL", "WEBAPP_URL2", "PD_POLICY_URL"
    )(_https)

    @field_validator("ONEC_URL")
    @classmethod
    def _onec_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("должен начинаться с http:// или https://")
        return value.rstrip("/")

    @cached_property
    def admin_ids(self) -> set[str]:
        return {x.strip() for x in self.ADMIN_IDS.split(",") if x.strip()}

    @property
    def db_file(self) -> Path:
        path = Path(self.DB_PATH)
        return path if path.is_absolute() else BASE_DIR / path

    @property
    def log_dir(self) -> Path:
        path = Path(self.LOG_DIR)
        return path if path.is_absolute() else BASE_DIR / path


def load_settings() -> Settings:
    """Читает настройки; при ошибке печатает имена полей и завершает процесс (FR-013)."""
    try:
        return Settings()
    except ValidationError as exc:
        fields = sorted({str(err["loc"][0]) for err in exc.errors() if err.get("loc")})
        print(
            "Ошибка настроек (.env): проверьте переменные: " + ", ".join(fields),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
