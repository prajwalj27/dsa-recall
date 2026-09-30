from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """App configuration, read from environment variables and the repo's `.env` file."""

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    leetcode_username: str = ""
    leetcode_session: str = ""
    leetcode_csrftoken: str = ""

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_model_solution: str = ""

    database_path: Path = Path("data/dsa-recall.db")
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def resolved_database_path(self) -> Path:
        path = self.database_path
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.resolved_database_path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
