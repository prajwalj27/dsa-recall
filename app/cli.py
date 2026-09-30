"""Shared setup for the command-line tools."""

import argparse
import sys

from app.config import ENV_VAR, ROOT_DIR, Settings, env_set_in_dotenv, get_settings, use_env


def add_env_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--prod",
        action="store_true",
        help="use the prod database (default: dev)",
    )


def describe(settings: Settings) -> str:
    path = settings.resolved_database_path
    try:
        shown = path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        shown = str(path)
    return f"{settings.env} database ({shown})"


def select_env(prod: bool) -> Settings:
    """Dev unless --prod (or DSA_RECALL_ENV=prod in the shell). Prints which DB is used."""
    if env_set_in_dotenv():
        print(
            f"Warning: {ENV_VAR} is set in .env; remove it so dev stays the default.",
            file=sys.stderr,
        )
    settings = use_env("prod" if prod else get_settings().env)
    print(f"Using {describe(settings)}", flush=True)
    return settings
