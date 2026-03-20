from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    return Path.home() / ".local" / "share" / "moonstone"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MOONSTONE_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default_factory=_default_data_dir)

    host: str = "127.0.0.1"
    port: int = 8000

    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    allow_local_execution: bool = True
    default_backend: str = "dummy"


_GLOBAL_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    global _GLOBAL_SETTINGS
    if _GLOBAL_SETTINGS is None:
        _GLOBAL_SETTINGS = Settings()
    return _GLOBAL_SETTINGS
