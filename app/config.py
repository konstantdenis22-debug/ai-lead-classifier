from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ROUTERAI_API_KEY: str = ""
    ROUTERAI_BASE_URL: str = "https://routerai.ru/api/v1"
    MODEL_ID: str = "x-ai/grok-4.20"

    PROMPT_VERSION: str = "v1.0.0"
    SCHEMA_VERSION: str = "v1.0.0"

    MAX_RETRIES: int = 1
    REQUEST_TIMEOUT: float = 60.0
    TEMPERATURE: float = 0.2

    LOG_DIR: str = "logs"
    REPORTS_DIR: str = "reports"

    # Optional mock mode for offline development
    MOCK_LLM: bool = False

    @property
    def log_path(self) -> Path:
        path = Path(self.LOG_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def reports_path(self) -> Path:
        path = Path(self.REPORTS_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
