"""Application settings."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    secret_key: str = "dev-secret-not-for-production"
    database_url: str = f"sqlite+aiosqlite:///{ROOT / 'sanctuary.db'}"
    redis_url: str | None = None
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://tenshinarts.com",
        "https://www.tenshinarts.com",
    ]
    ruleset_root: Path = ROOT / "rulesets"
    module_root: Path = ROOT / "modules"
    tenshin_secret: str | None = None
    tenshin_site_url: str = "https://tenshinarts.com"
    tenshin_dev: bool = False
    tenshin_dev_account: int = 1
    sanctuary_admin_ids: str | None = None
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    ollama_enabled: bool = True
    ollama_timeout: float = 5.0
    pixellab_host: str | None = None
    pixellab_model: str = "flux"


SETTINGS = Settings()
