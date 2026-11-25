"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Comma-separated API keys: "key1,key2"
    llm_api_keys: str = ""

    # LiteLLM model string, e.g. "gemini/gemini-3.5-flash-lite"
    llm_model: str = "gemini/gemini-3.5-flash-lite"

    # SQLite connection string
    database_url: str = "sqlite:////data/app.db"

    # Comma-separated allowed CORS origins
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # Feature flag: enable X-Simulate-Failure header
    enable_failure_simulation: bool = True

    # Optional default system prompt
    default_system_prompt: str = "You are a helpful AI assistant."

    @property
    def api_keys(self) -> List[str]:
        """Return list of non-empty API keys."""
        return [k.strip() for k in self.llm_api_keys.split(",") if k.strip()]

    @property
    def cors_origins(self) -> List[str]:
        """Return list of allowed CORS origins."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def db_path(self) -> str:
        """Extract filesystem path from sqlite:/// URL."""
        url = self.database_url
        if url.startswith("sqlite:////"):
            return "/" + url[len("sqlite:////"):]
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        return url


def get_settings() -> Settings:
    return Settings()

get_settings.cache_clear = lambda: None  # compatibility with tests
