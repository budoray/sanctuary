"""Shared pydantic-settings base for Tenshin Arts apps.

Canonical source: website/dropins/ — sync with deploy/sync-dropins.sh.
Each app extends TenshinSettings with FLEET_PORT and app-specific fields.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TenshinSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    tenshin_secret: str = Field(default="", validation_alias="TENSHIN_SECRET")
    tenshin_site_url: str = Field(
        default="https://tenshinarts.com", validation_alias="TENSHIN_SITE_URL")
    tenshin_cookie_domain: str | None = Field(
        default=None, validation_alias="TENSHIN_COOKIE_DOMAIN")
    load_host: str = Field(default="127.0.0.1", validation_alias="LOAD_HOST")
    load_port: int = Field(default=10000, validation_alias="LOAD_PORT")
    cookie_secure: bool = Field(default=True, validation_alias="COOKIE_SECURE")
