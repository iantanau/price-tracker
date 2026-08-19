"""Application settings loaded from environment variables.

All configurable values are centralised here so no other module contains
hard-coded configuration. Use ``get_settings()`` to obtain a cached instance.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values are read from environment variables. An optional ``.env`` file is
    also supported for local development. SMTP settings are required for the
    EmailNotifier; the application will continue to run if they are missing,
    but email delivery will fail until they are provided.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # HTTP client settings
    http_timeout: int = Field(default=30, description="Request timeout in seconds")
    http_retries: int = Field(default=3, description="Number of retries for failed requests")
    http_user_agent: str = Field(
        default="PriceTracker/0.1.0",
        description="User-Agent header sent with every HTTP request",
    )
    http_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Additional HTTP headers provided as a JSON object",
    )

    # Email notifier settings
    smtp_host: str = Field(default="", description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: str = Field(default="", description="SMTP authentication username")
    smtp_password: str = Field(default="", description="SMTP authentication password")
    smtp_security: Literal["SSL", "STARTTLS", "NONE"] = Field(
        default="STARTTLS",
        description="SMTP transport security: SSL (port 465), STARTTLS (port 587), or NONE",
    )
    smtp_from: str = Field(default="", description="From email address")
    smtp_to: str = Field(default="", description="Comma-separated list of recipient email addresses")

    # Supabase / PostgreSQL storage settings
    supabase_database_url: str = Field(
        default="",
        description="Supabase/PostgreSQL connection string (Supavisor transaction pooler)",
    )

    # Application settings
    log_level: str = Field(default="INFO", description="Logging level")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Caching avoids re-parsing environment variables on every call.

    Returns:
        The application settings.
    """
    return Settings()
