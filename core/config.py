"""
core/config.py
─────────────────────────────────────────────────────────────────────────────
Centralised settings using Pydantic-Settings.  Values are read from the
environment (or .env file) automatically.
"""

from functools import lru_cache
from typing import List
import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Detexa"
    app_version: str = "1.0.0"
    app_env: str = "development"

    # ── Security ─────────────────────────────────────────────────────────────
    secret_key: str = "change-me-in-production-at-least-32-characters"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = os.getenv("DATABASE_URL")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = os.getenv("REDIS_URL")

    # ── API ──────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: List[str] = ["http://localhost:8501", "http://localhost:3000"]

    # ── ML / Risk Thresholds ─────────────────────────────────────────────────
    model_path: str = "ml/models/saved"
    fraud_threshold: float = 0.5
    high_risk_threshold: float = 0.75

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
