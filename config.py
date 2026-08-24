"""Sanctuary settings."""
from __future__ import annotations

from pydantic import Field

from tenshin_config import TenshinSettings


class Settings(TenshinSettings):
    load_port: int = Field(default=10600, validation_alias="LOAD_PORT")
    decision_timeout_seconds: int = Field(
        default=60, validation_alias="DECISION_TIMEOUT_SECONDS"
    )


settings = Settings()
  # type: ignore[call-arg]  # values come from .env at runtime