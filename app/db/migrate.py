import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.config import BACKUP_DIR, Settings

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
KEEP_AUTO_BACKUPS = 5


def alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("path_separator", "os")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def upgrade_to_head(url: str) -> None:
    """Apply all pending migrations, so users never run Alembic by hand."""
    command.upgrade(alembic_config(url), "head")


def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config("sqlite://")).get_current_head()


def current_revision(url: str) -> str | None:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def pending_revisions(url: str) -> list[str]:
    """Revisions not yet applied to this database, oldest first."""
    script = ScriptDirectory.from_config(alembic_config(url))
    current = current_revision(url)
    pending = script.iterate_revisions(script.get_current_head(), current)
    return [rev.revision for rev in reversed(list(pending))]


def backup_database(src: Path, label: str, backup_dir: Path = BACKUP_DIR) -> Path:
    """Copy a SQLite DB with the online backup API (safe while the app has it open)."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"{src.stem}-{stamp}-{label}.db"
    with (
        closing(sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)) as source,
        closing(sqlite3.connect(dest)) as target,
    ):
        source.backup(target)
    return dest


def prune_auto_backups(src: Path, backup_dir: Path = BACKUP_DIR, keep: int = KEEP_AUTO_BACKUPS):
    """Keep the newest `keep` automatic (pre-migration) backups; manual ones are never pruned."""
    auto = sorted(backup_dir.glob(f"{src.stem}-*-before-*.db"))
    for old in auto[:-keep] if keep else auto:
        old.unlink()


def prepare_database(settings: Settings, backup_dir: Path = BACKUP_DIR) -> Path | None:
    """Bring the DB to the latest schema. Every entry point calls this.

    Prod is backed up first if migrations are pending, so a bad migration can always be
    undone by restoring the file. Returns the backup's path, if one was made.
    """
    path = settings.resolved_database_path
    url = settings.database_url
    backup = None
    if settings.env == "prod" and path.exists() and pending_revisions(url):
        backup = backup_database(path, f"before-{head_revision()}", backup_dir)
        prune_auto_backups(path, backup_dir)
        log.warning("Backed up %s to %s before migrating", path.name, backup)
    upgrade_to_head(url)
    return backup
