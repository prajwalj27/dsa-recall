"""Manage the dev and prod databases.

python -m app.db status                 # both DBs, schema versions, row counts, backups
python -m app.db copy-prod-to-dev       # fresh dev copy of the real data (prod is only read)
python -m app.db backup [--dev]         # manual backup into data/backups/ (default: prod)
"""

import argparse
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

from app.config import BACKUP_DIR, ENV_VAR, ROOT_DIR, Env, Settings
from app.db.migrate import backup_database, head_revision, prepare_database

COUNTED_TABLES = ("problems", "solves", "cards")


def settings_for(env: Env) -> Settings:
    return Settings(**{ENV_VAR: env})


def _shown(path: Path) -> str:
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return str(path)


def read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def describe_database(path: Path) -> dict:
    """Read-only summary; never creates the file."""
    if not path.exists():
        return {"exists": False}
    with closing(read_only(path)) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        revision = (
            conn.execute("SELECT version_num FROM alembic_version").fetchone()
            if "alembic_version" in tables
            else None
        )
        counts = {
            t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in COUNTED_TABLES
            if t in tables
        }
    return {
        "exists": True,
        "size_kb": path.stat().st_size // 1024,
        "revision": revision[0] if revision else None,
        "counts": counts,
    }


def copy_database(src: Path, dest: Path) -> None:
    """Snapshot src into dest with SQLite's backup API. src is opened read-only."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with closing(read_only(src)) as source, closing(sqlite3.connect(dest)) as target:
        source.backup(target)


def cmd_status() -> int:
    head = head_revision()
    for env in ("prod", "dev"):
        path = settings_for(env).resolved_database_path
        info = describe_database(path)
        print(f"{env:>4}: {_shown(path)}")
        if not info["exists"]:
            print("      not created yet")
            continue
        pending = "" if info["revision"] == head else f" (latest is {head}; migrates on next start)"
        counts = ", ".join(f"{v} {k}" for k, v in info["counts"].items())
        print(f"      {info['size_kb']} KB, schema {info['revision']}{pending}")
        print(f"      {counts}")
    backups = sorted(BACKUP_DIR.glob("*.db")) if BACKUP_DIR.exists() else []
    print(f"backups: {len(backups)} in {_shown(BACKUP_DIR)}")
    for b in backups[-10:]:
        stamp = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"      {b.name}  ({b.stat().st_size // 1024} KB, {stamp})")
    return 0


def cmd_copy_prod_to_dev(yes: bool) -> int:
    prod, dev = settings_for("prod"), settings_for("dev")
    src, dest = prod.resolved_database_path, dev.resolved_database_path
    if src == dest:
        print("Prod and dev point at the same file (DATABASE_PATH is set); refusing.")
        return 1
    if not src.exists():
        print(f"No prod database at {_shown(src)} yet.")
        return 1
    if dest.exists() and not yes:
        if not sys.stdin.isatty():
            print(f"{_shown(dest)} exists; pass --yes to replace it.")
            return 1
        answer = input(f"Replace {_shown(dest)} with a copy of prod? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return 1
    copy_database(src, dest)
    prepare_database(dev)  # migrate the copy: a rehearsal of what prod will go through
    counts = describe_database(dest)["counts"]
    print(f"Copied prod into {_shown(dest)}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return 0


def cmd_backup(env: Env) -> int:
    path = settings_for(env).resolved_database_path
    if not path.exists():
        print(f"No {env} database at {_shown(path)}.")
        return 1
    dest = backup_database(path, "manual")
    print(f"Backed up {_shown(path)} to {_shown(dest)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.db", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="both databases, schema versions, row counts, backups")
    copy = sub.add_parser("copy-prod-to-dev", help="replace dev with a copy of prod")
    copy.add_argument("--yes", action="store_true", help="don't ask before replacing dev")
    backup = sub.add_parser("backup", help="manual backup into data/backups/")
    backup.add_argument("--dev", action="store_true", help="back up dev instead of prod")
    args = parser.parse_args(argv)

    match args.command:
        case "status":
            return cmd_status()
        case "copy-prod-to-dev":
            return cmd_copy_prod_to_dev(args.yes)
        case "backup":
            return cmd_backup("dev" if args.dev else "prod")
    return 1


if __name__ == "__main__":
    sys.exit(main())
