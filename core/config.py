"""Pydantic-based settings management.

This module provides typed application settings loaded from environment
variables. All settings are validated at startup with no insecure fallbacks.
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings with strict validation.

    All settings are loaded from environment variables with no insecure
    fallback values. Missing required settings will cause startup to fail.
    """

    # Security
    webhook_secret: str = Field(
        ...,
        min_length=24,
        description="Bearer token for webhook authentication (min 24 chars)",
    )

    # Environment
    environment: str = Field(
        default="production",
        pattern="^(development|production|testing)$",
        description="Runtime environment (development enables docs)",
    )

    # Google Calendar
    google_calendar_id: str = Field(
        default="primary",
        description="Calendar ID for event creation",
    )
    google_credentials_path: str = Field(
        default="credentials.json",
        description="Path to Google service account credentials",
    )

    # Timezone and Defaults
    timezone: str = Field(
        default="UTC",
        description="Default timezone for events",
    )
    default_event_duration_minutes: int = Field(
        default=60,
        ge=1,
        description="Default meeting duration in minutes",
    )
    default_event_title: str = Field(
        default="Meeting",
        min_length=1,
        description="Default title when none provided",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging verbosity level",
    )

    @field_validator("webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, v: str) -> str:
        """Ensure webhook secret meets security requirements.

        Args:
            v: The webhook secret value

        Returns:
            str: Validated secret

        Raises:
            ValueError: If secret is missing or too short
        """
        if not v:
            raise ValueError("WEBHOOK_SECRET is required and cannot be empty")
        if len(v) < 24:
            raise ValueError("WEBHOOK_SECRET must be at least 24 characters")
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance (initialized on first import via _load_settings)
_settings: Optional[Settings] = None


def _load_settings() -> Settings:
    """Load settings from environment with validation.

    This function provides a wrapper for settings initialization,
    allowing for better error handling during startup.

    Returns:
        Settings: Validated application settings

    Raises:
        ValueError: If required settings are missing or invalid
    """
    try:
        return Settings()  # type: ignore[call-arg]  # Loaded from environment by pydantic-settings
    except Exception as e:
        # Re-raise with more context
        raise ValueError(f"Failed to load settings: {e}") from e


def get_settings() -> Settings:
    """Get the application settings singleton.

    Returns:
        Settings: The validated application settings instance.
    """
    global _settings
    if _settings is None:
        _settings = _load_settings()
    return _settings
