"""Dev and prod databases (plan 006): path resolution, env selection, backups, copying."""

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient

from app.cli import select_env
from app.config import ENV_VAR, Settings, env_set_in_dotenv, get_settings, use_env
from app.db import __main__ as db_cli
from app.db.migrate import (
    alembic_config,
    head_revision,
    pending_revisions,
    prepare_database,
    prune_auto_backups,
)
from app.db.session import get_engine


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """No env or path overrides; restored (with caches cleared) afterwards."""
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.setenv(ENV_VAR, "dev")  # registered so monkeypatch restores it after use_env
    monkeypatch.delenv(ENV_VAR)
    yield monkeypatch
    get_settings.cache_clear()
    get_engine.cache_clear()


def settings(env: str, path: Path) -> Settings:
    return Settings(_env_file=None, database_path=path, **{ENV_VAR: env})


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migrated_db(path: Path, revision: str = "head", rows: int = 1) -> Path:
    command.upgrade(alembic_config(f"sqlite:///{path.as_posix()}"), revision)
    with closing(sqlite3.connect(path)) as conn:
        for i in range(rows):
            conn.execute(
                "INSERT INTO problems (slug, title, difficulty, topic_tags, similar_questions, "
                "is_paid_only) VALUES (?, 'T', 'Easy', '[]', '[]', 0)",
                (f"p{i}",),
            )
        conn.commit()
    return path


# --- Resolution -------------------------------------------------------------------------------


def test_default_is_dev(clean_env) -> None:
    s = Settings(_env_file=None)
    assert (s.env, s.resolved_database_path.name) == ("dev", "dsa-recall.dev.db")


def test_prod_uses_the_original_file(clean_env) -> None:
    clean_env.setenv(ENV_VAR, "prod")
    assert Settings(_env_file=None).resolved_database_path.name == "dsa-recall.db"


def test_database_path_overrides_both(clean_env, tmp_path) -> None:
    clean_env.setenv("DATABASE_PATH", str(tmp_path / "x.db"))
    for env in ("dev", "prod"):
        clean_env.setenv(ENV_VAR, env)
        assert Settings(_env_file=None).resolved_database_path == tmp_path / "x.db"


def test_use_env_switches_settings_and_engine(clean_env) -> None:
    assert use_env("prod").env == "prod"
    assert get_engine().url.database.endswith("dsa-recall.db")
    assert use_env("dev").env == "dev"
    assert get_engine().url.database.endswith("dsa-recall.dev.db")


def test_dotenv_must_not_choose_env(tmp_path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("LEETCODE_USERNAME=x\n")
    assert not env_set_in_dotenv(dotenv)
    dotenv.write_text("LEETCODE_USERNAME=x\nDSA_RECALL_ENV=prod\n")
    assert env_set_in_dotenv(dotenv)


def test_cli_reports_which_database(clean_env, capsys) -> None:
    select_env(prod=False)
    select_env(prod=True)
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "Using dev database (data/dsa-recall.dev.db)",
        "Using prod database (data/dsa-recall.db)",
    ]


def test_health_reports_env(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["env"] == "dev"
    assert body["database"] == "test.db"


# --- Backups before migrations -----------------------------------------------------------------


def test_prod_backs_up_before_pending_migration(tmp_path) -> None:
    db = migrated_db(tmp_path / "prod.db", revision="0002")
    backups = tmp_path / "backups"

    backup = prepare_database(settings("prod", db), backup_dir=backups)

    assert backup is not None and backup.parent == backups
    assert f"before-{head_revision()}" in backup.name
    with closing(sqlite3.connect(backup)) as conn:  # restorable: old schema, same rows
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"
        assert conn.execute("SELECT count(*) FROM problems").fetchone()[0] == 1
    assert pending_revisions(f"sqlite:///{db.as_posix()}") == []


def test_no_backup_when_nothing_pending(tmp_path) -> None:
    db = migrated_db(tmp_path / "prod.db")
    assert prepare_database(settings("prod", db), backup_dir=tmp_path / "backups") is None
    assert not (tmp_path / "backups").exists()


def test_dev_never_backs_up(tmp_path) -> None:
    db = migrated_db(tmp_path / "dev.db", revision="0002")
    assert prepare_database(settings("dev", db), backup_dir=tmp_path / "backups") is None
    assert not (tmp_path / "backups").exists()


def test_new_prod_database_needs_no_backup(tmp_path) -> None:
    db = tmp_path / "fresh.db"
    assert prepare_database(settings("prod", db), backup_dir=tmp_path / "backups") is None
    assert db.exists()


def test_prune_keeps_newest_automatic_backups_only(tmp_path) -> None:
    src = tmp_path / "dsa-recall.db"
    auto = [tmp_path / f"dsa-recall-2026010{i}-000000-before-0004.db" for i in range(1, 8)]
    manual = tmp_path / "dsa-recall-20250101-000000-manual.db"
    other = tmp_path / "dsa-recall.dev-20250101-000000-before-0004.db"
    for f in (*auto, manual, other):
        f.write_text("x")

    prune_auto_backups(src, backup_dir=tmp_path, keep=5)

    assert sorted(p.name for p in tmp_path.glob("dsa-recall-*-before-*.db")) == [
        p.name for p in auto[2:]
    ]
    assert manual.exists() and other.exists()


# --- Copy prod to dev -----------------------------------------------------------------------------


def test_copy_prod_to_dev_reads_prod_only(tmp_path, monkeypatch) -> None:
    prod = migrated_db(tmp_path / "prod.db", rows=3)
    dev = tmp_path / "dev.db"
    before = sha(prod)
    monkeypatch.setattr(
        db_cli, "settings_for", lambda env: settings(env, prod if env == "prod" else dev)
    )

    assert db_cli.main(["copy-prod-to-dev"]) == 0

    assert sha(prod) == before
    assert db_cli.describe_database(dev)["counts"]["problems"] == 3


def test_copy_refuses_to_replace_dev_without_yes(tmp_path, monkeypatch) -> None:
    prod = migrated_db(tmp_path / "prod.db", rows=3)
    dev = migrated_db(tmp_path / "dev.db", rows=1)
    monkeypatch.setattr(
        db_cli, "settings_for", lambda env: settings(env, prod if env == "prod" else dev)
    )

    assert db_cli.main(["copy-prod-to-dev"]) == 1  # stdin isn't a terminal under pytest
    assert db_cli.describe_database(dev)["counts"]["problems"] == 1
    assert db_cli.main(["copy-prod-to-dev", "--yes"]) == 0
    assert db_cli.describe_database(dev)["counts"]["problems"] == 3


def test_describe_never_creates_a_file(tmp_path) -> None:
    missing = tmp_path / "nope.db"
    assert db_cli.describe_database(missing) == {"exists": False}
    assert not missing.exists()
