import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"

Env = Literal["dev", "prod"]
ENV_VAR = "DSA_RECALL_ENV"

# Prod keeps the original file name, so existing real data stays where it is.
DEFAULT_DB_PATHS: dict[str, Path] = {
    "prod": DATA_DIR / "dsa-recall.db",
    "dev": DATA_DIR / "dsa-recall.dev.db",
}


class Settings(BaseSettings):
    """App configuration, read from environment variables and the repo's `.env` file."""

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    # dev unless chosen explicitly: only the `dsa-recall` launcher and `--prod` flags pick prod.
    env: Env = Field(default="dev", validation_alias=ENV_VAR)

    leetcode_username: str = ""
    leetcode_session: str = ""
    leetcode_csrftoken: str = ""

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_model_solution: str = ""

    database_path: Path | None = None  # explicit override (tests); else per-env default
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def resolved_database_path(self) -> Path:
        path = self.database_path or DEFAULT_DB_PATHS[self.env]
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.resolved_database_path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def use_env(env: Env) -> Settings:
    """Select dev or prod for this process (and its children) before touching the DB."""
    os.environ[ENV_VAR] = env
    get_settings.cache_clear()
    # Imported here to avoid a cycle: the session module reads settings.
    from app.db.session import get_engine, get_sessionmaker

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    return get_settings()


def env_set_in_dotenv(dotenv: Path = ROOT_DIR / ".env") -> bool:
    """`.env` should never choose the environment; that would silently make prod the default."""
    if not dotenv.is_file():
        return False
    return any(line.strip().startswith(f"{ENV_VAR}=") for line in dotenv.read_text().splitlines())
