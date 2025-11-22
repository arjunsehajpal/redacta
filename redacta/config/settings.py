from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Redacta configuration settings.

    Settings can be configured via environment variables with the REDACTA_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="REDACTA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    enable_pii_protection: bool = True
    spacy_model: str = "en_core_web_sm"
    local_key_path: str = "./redacta.key"

    @property
    def key_path(self) -> Path:
        """Return the key path as a Path object."""
        return Path(self.local_key_path)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Cached Settings instance
    """
    return Settings()
