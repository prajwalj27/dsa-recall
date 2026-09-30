# 006 — Separate dev and prod databases

## Context

Everything currently uses one SQLite file, `data/dsa-recall.db`: the real app, `uvicorn --reload` during development, the sync and review CLIs, and Alembic. During plan 005's verification, a check meant for a copy of the database reached the user's dev server instead and wrote into the real data (reverted from a backup). That was avoidable, and it will get riskier as later plans add migrations and LLM-written data. The user wants **prod to stay untouched by dev tests and changes**. This plan comes before the LLM pipeline.

**Decisions made:**

- **Dev by default.** Only the `dsa-recall` launcher uses prod. `uvicorn --reload`, `npm run dev` (through its backend), `python -m app.sync`, `python -m app.engines.reviews`, `python -m app.leetcode.smoke`, and Alembic all use the dev DB unless `--prod` is passed (or `DSA_RECALL_ENV=prod` is set in the shell). Forgetting a flag can only ever touch dev.
- **Dev starts as a copy of prod, refreshable on demand.** `python -m app.db copy-prod-to-dev` snapshots prod into dev. Prod is only read, and the copy is safe even while `dsa-recall` is running.
- **Automatic prod backup before migrations.** When prod has a pending migration (a script that changes the database's structure), the app copies the DB to `data/backups/` just before applying it, keeping the last 5. Normal starts do nothing extra. New migrations are also exercised on the dev copy first, while we build.

## Design

### Environment and paths (`app/config.py`)

- `Settings.env: Literal["dev", "prod"] = "dev"`, read from `DSA_RECALL_ENV`.
- `Settings.database_path: Path | None`. An explicit `DATABASE_PATH` still wins (tests use it for temp DBs). Otherwise:
  - prod → `data/dsa-recall.db` (the existing file, so real data stays where it is)
  - dev → `data/dsa-recall.dev.db`
- `use_env(env)`: sets `DSA_RECALL_ENV` for this process (and child processes such as uvicorn's reload workers) and clears the cached settings, engine, and sessionmaker. Every entry point calls it before touching the DB.
- **`.env` must not set `DSA_RECALL_ENV`.** Otherwise the default would silently become prod. `.env.example` says so, and the app logs a warning at startup if `.env` contains it.

### Entry points

| Entry point | Environment |
| --- | --- |
| `dsa-recall` (the launcher, serves the built UI) | **prod** |
| `uvicorn app.main:app --reload` / `npm run dev` | dev |
| `python -m app.sync [--full] [--prod]` | dev unless `--prod` |
| `python -m app.engines.reviews … [--prod]` | dev unless `--prod` |
| `python -m app.leetcode.smoke` | no DB (reads LeetCode only) |
| `alembic …` | dev (via `env.py` → settings) |
| `pytest` | temp DBs via `DATABASE_PATH` (unchanged) |

### Migrations with backup (`app/db/migrate.py`)

- `pending_revisions(url)` compares the DB's current revision with the scripts' head.
- `prepare_database(settings)` is the single function every entry point calls instead of `upgrade_to_head`. If there are pending revisions, `env == "prod"`, and the file already exists, it first backs up to `data/backups/dsa-recall-<YYYYmmdd-HHMMSS>-before-<head>.db` using SQLite's online backup API, then keeps the newest 5. Then it upgrades. Dev never backs up; recreating it takes one command.

### `python -m app.db` (new CLI)

- **`status`:** both databases' paths, sizes, schema revisions (plus "N pending"), and row counts (problems, solves, cards), plus the backups on disk. Read-only.
- **`copy-prod-to-dev [--yes]`:** prod (opened read-only) → dev via the SQLite backup API; asks for confirmation if dev exists, unless `--yes`. It then applies any pending migrations to the dev copy, which doubles as a rehearsal of what prod will go through.
- **`backup [--prod|--dev]`:** a manual backup into `data/backups/` (default prod).

### Making the environment visible

- `GET /api/health` → `{status, version, env, database}` (the database's file name, not the full path).
- **UI:** in dev, the sidebar header shows a **DEV** badge next to "DSA Recall", and the tab title gets a `[dev]` prefix ("[dev] (72) DSA Recall"). Prod shows nothing extra.
- CLIs print the environment and database file on their first line, e.g. `Using dev database (data/dsa-recall.dev.db)`.

### Docs

- README: a short "Dev and prod data" section covering which command uses which database, `copy-prod-to-dev`, and backups.
- The existing `.gitignore` already ignores `data/` and `*.db`.

## Tests

- **Settings resolution:** default dev path; `DSA_RECALL_ENV=prod` → prod path; `DATABASE_PATH` overrides both; `use_env` clears caches so the engine points at the new file.
- **`prepare_database`:**
  - Prod with a pending migration → exactly one backup, and a restorable one (opens, correct revision and rows).
  - Nothing pending → no backup.
  - Dev → never backs up.
  - Pruning keeps 5.
- **`copy-prod-to-dev`:** the copy has prod's rows; prod's bytes are unchanged; it refuses to overwrite without `--yes` when not interactive.
- **CLIs:** `--prod` selects prod and the default selects dev (checked through the printed first line, using temp paths for both).
- **`/api/health`** reports `env`.

## Verification

1. `pytest`, `ruff`, `npm run lint`, `npm test`, and `npm run build` are clean.
2. `python -m app.db status` → prod = the existing file (94 cards, revision 0003), dev = missing.
3. `python -m app.db copy-prod-to-dev` → dev has the same counts; prod's checksum and modification time are unchanged.
4. `uvicorn app.main:app --reload` → `/api/health` says `dev`, and the UI shows the DEV badge and `[dev]` title. Marking a review there changes dev only (prod's checksum is unchanged).
5. `dsa-recall` → `/api/health` says `prod`, with no badge. `python -m app.sync` without flags reports the dev database.
6. **Backup path:** simulated on temp files in tests. Live, it happens the next time a plan adds a migration: prod then backs up once on its first start.
7. **Before any of this, stop at a checkpoint:** I'll ask you to stop your own dev server on :8000, so nothing is holding the prod file while it becomes "prod only".

## Outcome (implemented 2026-09-30)

Implemented as planned:

- `Settings.env` and `use_env` in `app/config.py`
- `prepare_database`, pre-migration backups, and pruning in `app/db/migrate.py`
- `python -m app.db` (`status`, `copy-prod-to-dev`, `backup`) in `app/db/__main__.py`
- `--prod` for the sync and review CLIs via `app/cli.py`
- `/api/health` reports `env` and `database`
- A DEV badge and `[dev]` tab title in the UI
- README section and `.env.example` note

There are 15 new tests (118 total). All of them use temp files, and `data/` is unchanged after `pytest`.

**Verified live** (prod files checksummed before, and re-checked after every step: unchanged throughout):

1. **Before:** `status` showed prod = `data/dsa-recall.db` (schema 0003, 97 problems, 170 solves, 94 cards), with dev not created yet.
2. **Copy:** `copy-prod-to-dev` gave dev the same counts, and prod was byte-identical afterwards.
3. **Default server:** a server started with no flags (port 8771, bind confirmed in its log) used dev per `/api/health`. A "mark reviewed" through it landed in dev only: 1 manual review in dev, 0 in prod.
4. **Launcher:** `run()` (the `dsa-recall` launcher, port 8772, browser disabled) used prod. `reviews due` with no flag used dev (71 due); with `--prod`, prod (72 due).
5. **UI:** in dev, the sidebar shows the DEV badge and the tab reads "[dev] (71) DSA Recall".
6. **Reset:** dev was refreshed from prod afterwards, so the test review is gone.
7. **Backups:** the pre-migration backup path is covered by tests on temp files. Live, it happens the next time a plan adds a migration.
