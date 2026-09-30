# DSA Recall — Project setup plan

## Context
The repo is empty apart from `README.md` and `docs/DSA Recall - Design.md`. The design fixes the core stack: FastAPI, SQLAlchemy/SQLite, py-fsrs, Pydantic, React, react-force-graph-2d, and pytest. It also fixes the repo layout (`app/`, `web/`, `tests/`) and a 5-step feature build order. Before starting build step 1 (Sync + reviews), we need a working skeleton: a backend and a frontend that run together, a database with migrations, config loading, and dev tooling. That way, every feature step adds code to a working base.

**Choices made:** pip + venv (with `pyproject.toml`), Vite + React + TypeScript, Tailwind + shadcn/ui, and Alembic migrations from day one.
**Defaults assumed:** Python 3.12, Node 20, npm, sync SQLAlchemy 2.0 with `httpx` (a single-user local app gains nothing from async; background sync can run in a thread), `pydantic-settings` for `.env`, ruff for Python lint/format, and ESLint + Prettier for the web app.

## Setup order (each phase leaves something runnable)

### Phase 0 — Repo hygiene
- `.gitignore`: `.venv/`, `__pycache__/`, `.env`, `*.db`, `data/`, `web/node_modules/`, `web/dist/`, `.pytest_cache/`, `.ruff_cache/`
- `.env.example`: exactly the keys from the design doc, with OpenRouter and Ollama samples
- `.editorconfig` (LF, UTF-8, 4 spaces for py, 2 for ts)
- Expand `README.md`: what the app is, prerequisites, and the dev commands below

### Phase 1 — Backend skeleton
- `pyproject.toml` (setuptools): runtime deps `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2`, `alembic`, `pydantic>=2`, `pydantic-settings`, `httpx`, `fsrs` (py-fsrs), `openai` (the OpenAI-compatible client); `[dev]` extras `pytest`, `ruff`. Console script `dsa-recall = app.main:run`.
- Workflow: `python -m venv .venv` → `.venv\Scripts\activate` → `pip install -e ".[dev]"`
- Package layout from the design doc, each directory with an `__init__.py`:
  `app/{leetcode,sync,llm,engines,db,api}/`, plus:
  - `app/config.py`: a `Settings(BaseSettings)` class that reads `.env` (LeetCode + LLM keys, `DATABASE_PATH` defaulting to `data/dsa-recall.db`)
  - `app/main.py`: `create_app()` mounts the `/api` router and serves `web/dist` (static files plus an SPA fallback to `index.html`) when it exists. `run()` starts uvicorn on `127.0.0.1:8000` and opens the browser.
  - `app/api/health.py`: `GET /api/health` returns `{status, version}`
- ruff config in `pyproject.toml`

### Phase 2 — Database + migrations
- `app/db/session.py`: engine (`sqlite:///...`), `SessionLocal`, `get_db` FastAPI dependency; enable `PRAGMA foreign_keys=ON` and WAL mode on connect (so the later notifier script can read safely)
- `app/db/models.py`: SQLAlchemy 2.0 declarative models for all **14 tables** in the design doc's data model (the schema is already designed, so one initial migration is simplest)
- `alembic init app/db/migrations`; `env.py` pulls the URL from `Settings` and `target_metadata` from `models`; enable `render_as_batch=True` (required for SQLite ALTERs)
- Generate `0001_initial` with autogenerate, then review it by hand
- On startup, `run()` applies `alembic upgrade head` so users never run migrations manually

### Phase 3 — Frontend skeleton (`web/`)
- `npm create vite@latest web -- --template react-ts`
- Tailwind v4 (`@tailwindcss/vite`) + `npx shadcn@latest init` (dark theme default); add the `button`, `card`, `table`, `sheet`, `badge`, `sidebar`, and `sonner` components as needed
- `react-router-dom`: layout with a sidebar (Today with due-count badge, Skill tree, Solved, Insights, Settings) and a top bar (Sync button + last-synced placeholder); one stub page per route
- `@tanstack/react-query` + a small `src/lib/api.ts` fetch wrapper; the Today stub calls `/api/health` to prove wiring
- `vite.config.ts`: dev proxy `/api` → `http://127.0.0.1:8000`; `@/` path alias (needed by shadcn)
- Defer `react-force-graph-2d` until build step 4

### Phase 4 — Run modes
- **Dev:** terminal 1 runs `uvicorn app.main:app --reload`; terminal 2 runs `npm run dev --prefix web` → open the Vite URL
- **Prod/local use:** `npm run build --prefix web`, then `dsa-recall` serves everything on `localhost:8000` (the "one command" from the design doc)
- Optional convenience: a root `Makefile` or `scripts/dev.ps1` later; not needed now

### Phase 5 — Tests & quality
- `tests/conftest.py`: a temp SQLite DB fixture that runs Alembic upgrade, plus a FastAPI `TestClient` fixture
- `tests/test_health.py` and `tests/test_migrations.py` (upgrade head succeeds and all 14 tables exist)
- `tests/fixtures/leetcode/`: an empty directory reserved for recorded GraphQL responses (step 1)
- Optional: a GitHub Actions workflow running `ruff check`, `pytest`, and `npm run build` + `npm run lint`

### Then: feature build step 1 (Sync + reviews)
Start with `app/leetcode/` (throttled httpx client, `userStatus` auth check, Pydantic schemas), using queries copied from DevTools as the design doc says. Its `tests/fixtures/leetcode/` recordings come next, then sync, FSRS cards, and the Today screen.

## Files created
`pyproject.toml`, `.gitignore`, `.env.example`, `.editorconfig`, `README.md`, `app/main.py`, `app/config.py`, `app/api/health.py`, `app/db/{session,models}.py`, `alembic.ini`, `app/db/migrations/`, `web/` (Vite app), `tests/{conftest,test_health,test_migrations}.py`

## Verification
1. `pip install -e ".[dev]"` succeeds in a fresh `.venv`; `ruff check .` is clean
2. `pytest` passes (health + migrations)
3. `uvicorn app.main:app --reload` → `GET http://127.0.0.1:8000/api/health` returns 200; `data/dsa-recall.db` exists with 14 tables + `alembic_version`
4. `npm run dev --prefix web` → all 5 sidebar routes render; Today shows the health status through the proxy
5. `npm run build --prefix web` then `dsa-recall` → the app loads at `localhost:8000`, and deep links such as `/solved` work (SPA fallback)
6. `git status` shows no `.env`, `.venv`, `node_modules`, `dist`, or `.db` files

## Outcome (implemented 2026-09-29)
Implemented as planned, with these differences:
- **Node upgraded** from 20.11 (EOL, too old for Vite 8) to 24.19 LTS via winget.
- **Linting:** the Vite template now ships **oxlint** instead of ESLint + Prettier, so we kept it. Generated shadcn files (`src/components/ui/**`, `src/hooks/use-mobile.ts`) are excluded from lint.
- **Versions:** Vite 8, React 19, TypeScript 6 (no `baseUrl`; `paths` only), react-router 8, Tailwind v4, shadcn (radix base, nova preset), SQLAlchemy 2.1, fsrs 6.
- **Migrations** run in the FastAPI lifespan (not only in `run()`), so `uvicorn --reload` and tests also get an up-to-date DB. `app/db/migrate.py` configures Alembic programmatically; the root `alembic.ini` is for the CLI.
- **Schema notes:** `solves.rating_inferred` is a bool flag (the rating was inferred, not chosen); `problem_analysis` gained `what_makes_it_hard`; `review_log.solve_id` is nullable for manual "Mark reviewed" events; `settings`/`sync_state` are key → JSON value tables.
- GitHub Actions CI was not added yet.
