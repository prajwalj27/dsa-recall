# DSA Recall

A local, open-source app that syncs your LeetCode history and turns it into spaced-repetition
reviews, suggestions for the skills you struggle with, and an LLM-built skill tree of what you've
learned. You keep solving on leetcode.com; DSA Recall only tracks.

See [the design doc](docs/DSA%20Recall%20-%20Design.md) for the full picture and
[docs/plans/](docs/plans/) for implementation plans, in order.

## Prerequisites

- Python 3.12+
- Node.js 22+ (LTS)
- An OpenAI-compatible LLM endpoint (OpenRouter, Ollama, ...)

## Setup

```powershell
# Backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# Frontend
npm install --prefix web

# Config
cp .env.example .env   # then fill in your LeetCode cookie and LLM settings
```

## Run

**Use the app** (one command, serves the built UI on http://127.0.0.1:8000):

```powershell
npm run build --prefix web
dsa-recall
```

**Develop** (hot reload on both sides; open the Vite URL, which proxies `/api` to the backend):

```powershell
uvicorn app.main:app --reload     # terminal 1
npm run dev --prefix web          # terminal 2
```

Databases are created and migrated automatically on startup; see *Dev and prod data* below.

## Dev and prod data

Two separate SQLite files, so development never touches your real history:

| Database | File | Used by |
| --- | --- | --- |
| **prod** | `data/dsa-recall.db` | `dsa-recall` (the real app), and tools run with `--prod` |
| **dev** | `data/dsa-recall.dev.db` | everything else: `uvicorn --reload`, `npm run dev`, `python -m app.sync`, `python -m app.engines.reviews`, `alembic` |

```powershell
python -m app.db status              # both databases, schema versions, row counts, backups
python -m app.db copy-prod-to-dev    # fresh dev copy of your real data (prod is only read)
python -m app.db backup              # manual prod backup into data/backups/
python -m app.sync --prod            # a tool on the real data, on purpose
```

In dev, the UI shows a **DEV** badge and the tab title starts with `[dev]`. Before prod applies
a new schema migration, it backs itself up to `data/backups/` automatically (last 5 kept).

## Checks

```powershell
ruff check . ; ruff format --check .
pytest
npm run lint --prefix web ; npm run build --prefix web
```

New database migration after changing `app/db/models.py`:

```powershell
alembic revision --autogenerate -m "describe change"
```

## Layout

```
app/
  leetcode/   LeetCode GraphQL client, queries, schemas, throttle
  sync/       backfill, incremental sync, grouping into solves
  llm/        provider adapter, prompts, the five tasks
  engines/    FSRS, mastery, recommender
  db/         models, session, Alembic migrations
  api/        FastAPI routes for the UI
web/          React + Vite + Tailwind + shadcn/ui frontend
tests/        pytest (recorded LeetCode responses in tests/fixtures/leetcode/)
docs/         design doc and numbered plans
```
