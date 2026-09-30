"""Run a sync in the terminal.

python -m app.sync           # backfill on first run, incremental afterwards
python -m app.sync --full    # walk every problem (manual resync)
python -m app.sync --prod    # the real database (default: dev)
"""

import argparse
import sys

from app.cli import add_env_flag, select_env
from app.db.migrate import prepare_database
from app.db.session import get_sessionmaker
from app.leetcode import LeetCodeClient
from app.sync.engine import run_sync
from app.sync.progress import RunState, SyncProgress


def _print_progress(progress: SyncProgress) -> None:
    if progress.phase == "problems" and progress.done:
        total = f"/{progress.total}" if progress.total else ""
        print(
            f"\r[{progress.done}{total}] +{progress.new_submissions} submissions, "
            f"+{progress.new_solves} solves",
            end="",
            flush=True,
        )
    elif progress.phase in ("auth", "listing", "scheduling"):
        prefix = "\n" if progress.phase == "scheduling" and progress.done else ""
        print(f"{prefix}{progress.phase}...", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.sync", description=__doc__)
    parser.add_argument("--full", action="store_true", help="walk every problem")
    add_env_flag(parser)
    args = parser.parse_args()

    settings = select_env(args.prod)
    prepare_database(settings)
    with LeetCodeClient(settings) as client:
        progress = run_sync(get_sessionmaker(), client, full=args.full, report=_print_progress)

    if progress.state is RunState.SUCCEEDED:
        print(
            f"Done ({progress.mode}): {progress.done} problems checked, "
            f"{progress.new_submissions} new submissions, {progress.new_solves} new solves, "
            f"{progress.scheduled} scheduled for review."
        )
        return 0
    print(f"Sync failed [{progress.error_kind}]: {progress.error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
