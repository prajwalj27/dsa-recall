# 003 — Sync (build step 1, part 2)

## Context

Plan 002 built `app/leetcode/`, a client that can read everything we need from LeetCode. This plan builds `app/sync/`, which uses that client to copy the user's LeetCode history into SQLite. It creates problems, submissions (with code), and **solves** (an accepted submission grouped with the failures before it). It covers both the first full load (backfill) and the cheap daily update (incremental). It also adds a way to start a sync and watch its progress.

FSRS cards, review replay, and inferred ratings are **plan 004**. They are computed from the `solves` this plan produces. The Today screen is plan 005.

**Decisions made:**

- **Solve grouping:** an accepted submission within **24 hours** of the current solve's first accept is merged into that solve (runtime tweaks and same-day resubmits don't count as extra reviews). The window is measured from the solve's first accept, so it can't chain forever.
- **Wrong attempts:** **every** non-accepted submission counts toward `wrong_before_ac`, including Compile Error.
- **Scope:** sync only. Solves are saved with `rating = NULL`; plan 004 infers or asks for ratings and builds cards.
- **Trigger:** API + CLI. `POST /api/sync` runs in a background thread (one at a time), `GET /api/sync/status` reports progress, and `python -m app.sync` runs it in the terminal.

## How the sync works

### One algorithm for backfill and incremental

The progress list (`iter_progress`) returns every problem touched, **newest `lastSubmittedAt` first** (verified in plan 002). For each problem, we store LeetCode's change markers (`last_submitted_at`, `num_submitted`) **in the same transaction** as that problem's submissions. So:

- A problem whose stored markers equal the remote ones is already fully synced; skip it with zero requests.
- **Backfill mode** (until `backfill_done` is true): walk the whole list and sync every changed problem. An interrupted backfill resumes automatically: finished problems are unchanged and skipped. No per-problem bookkeeping is needed.
- **Incremental mode:** walk from the newest and **stop at the first unchanged problem**. Everything after it is older and also unchanged.

After a full walk with no errors, `backfill_done = true`. Every successful sync sets `last_sync_at`.

### Syncing one changed problem (one DB transaction)

1. **Upsert the problem** from progress data: title, difficulty, tags, `frontend_id`, `question_status`, `last_result`.
2. If the problem is new (no `fetched_at`), call `question(slug)`: statement (null for paid-only), `ac_rate`, `similar_questions`, `is_paid_only`.
3. Call `submissions(slug)` newest first, and **stop at the first known submission ID**. Insert the new ones.
4. **Regroup** all of the problem's submissions with the pure grouping function (below). Insert solves whose `accepted_submission_id` isn't stored yet. Existing solves are never changed, so ratings attached in plan 004 stay put.
5. For each **new solve**, call `submission_detail` for its accepted submission and for **up to 3 failed attempts** before it. Store the `code` and a normalized `code_hash`. Merged extra accepts and older failures keep summary data only (no code), which saves requests.
6. Store the remote markers and commit.

Any `LeetCodeError` rolls back the current problem and **stops the sync** with the error recorded. For auth, rate-limit, or API-shape errors, continuing would just fail again. Problems already committed stay committed.

### Grouping submissions into solves (pure function)

Walk a problem's submissions oldest → newest:

- **Failure:** add it to the pending failures.
- **Accept within 24 h of the current solve's first accept:** merged; clear pending failures (they were part of the same session).
- **Any other accept:** a new solve with `wrong_before_ac = len(pending)`; remember the last 3 pending IDs for detail fetching; clear pending.

Failures left pending at the end mean "attempted since the last solve" (or never solved). That's shown on the Today screen later and computed on view.

### Expected cost

For the 97-problem account: about 2 progress pages, 97 `question` calls, about 100 submission lists, and roughly 300 detail calls. That's about **500 requests, or about 9 minutes** once. A typical daily sync is 1 progress page plus a few requests per changed problem.

## Changes

### Migration `0002`: `problems` gains sync fields

`frontend_id`, `is_paid_only` (default false), `question_status` (SOLVED/ATTEMPTED), `last_result`, `last_submitted_at`, `num_submitted`. All are nullable except `is_paid_only`; autogenerate, then review by hand.

### `app/sync/`

| File | Responsibility |
| --- | --- |
| `solves.py` | `group_solves(submissions) -> list[SolveSpec]`: the pure grouping function above (`MERGE_WINDOW = 24h`). |
| `codehash.py` | `code_hash(code)`: SHA-256 of code with trailing whitespace stripped, blank lines dropped, and indentation/space runs collapsed. Used later to skip re-analysis of identical re-solves. |
| `engine.py` | `run_sync(session_factory, client, progress, full=False)`: the walk and the per-problem transaction. `full=True` forces a backfill-style walk (the design doc's "manual resync"). All datetimes are stored as naive UTC. |
| `progress.py` | `SyncProgress` dataclass: `state` (idle/running/succeeded/failed), `mode`, `phase`, `done`, `total`, `current_slug`, `started_at`, `finished_at`, `error_kind` (auth_expired/rate_limited/schema_changed/other), `error`. Updated by the engine, read by the API. |
| `manager.py` | `SyncManager`: one per process. `start(full=False)` launches `run_sync` in a daemon thread unless one is already running (a lock); `status()` returns a snapshot. It builds its `LeetCodeClient` from `get_settings()` on each run, so a refreshed cookie in `.env` is picked up after restart. |
| `__main__.py` | `python -m app.sync [--full]`: applies migrations, runs the sync in the foreground, prints progress lines, and exits non-zero on failure. |

### `app/api/sync.py`

- `POST /api/sync?full=false` → 202 with the status (or the current status if a sync is already running)
- `GET /api/sync/status` → `SyncProgress` plus `last_sync_at` and `backfill_done` from `sync_state`

Registered in `app/api/__init__.py`. The lifespan doesn't auto-start a sync; "sync on app open" is triggered by the UI in plan 005.

### Reuse

- `LeetCodeClient`: `check_auth`, `iter_progress`, `submissions`, `submission_detail`, `question` (`app/leetcode/client.py`)
- The error classes in `app/leetcode/errors.py` map to `error_kind`
- `get_sessionmaker`/`get_engine` (`app/db/session.py`), `upgrade_to_head` (`app/db/migrate.py`), models in `app/db/models.py`
- `recent_accepted()` is **not** used. The first progress page (1 request) already covers new accepts *and* new failures.

## Tests (`tests/sync/`)

- **`FakeLeetCode`:** an in-memory stand-in with the same methods as `LeetCodeClient`, built from a small dict of problems and submissions. It counts calls per method and can raise a chosen error on the Nth call.
- **`group_solves`:** a single accept; failures then an accept (`wrong_before_ac`); accepts 3 minutes apart merge; accepts 25 hours apart don't; the window doesn't chain (0 h, 20 h, 40 h → two solves); failures between merged accepts are cleared; a Compile Error counts; failures only → no solves; last-3 failed IDs.
- **`code_hash`:** whitespace and blank-line changes → same hash; a real change → different hash.
- **Engine, on a temp DB:**
  - The backfill stores the expected problems, submissions, solves, and code, and sets `backfill_done`.
  - A second run makes only 1 progress request and 0 per-problem requests.
  - After one new submission, incremental stops at the first unchanged problem and appends exactly one solve without changing existing solve IDs.
  - A paid-only question stores a null statement.
  - An attempted-only problem stores failures and no solve.
- **Resume:** a `RateLimitedError` injected mid-backfill stops the sync, rolls back only the failing problem, and records `error_kind = rate_limited`. A rerun finishes, re-requesting only the unfinished problems.
- **Auth:** `check_auth` failing → state failed with `error_kind = auth_expired`, and nothing written.
- **API:** `POST /api/sync` returns 202; a second POST while running doesn't start another; `GET /api/sync/status` reflects the progress. Uses a manager wired to `FakeLeetCode`.

## Verification

1. `pytest` and `ruff check .` are clean, with no network access in tests.
2. **Live backfill (about 9 min, about 500 read-only requests at 1/s):** `python -m app.sync` against the real account.
   - `problems` count = 97, matching leetcode.com/progress.
   - Spot check: `longest-consecutive-sequence` has 15 submissions. Its accepts 3 minutes apart are merged, and its solve count and `wrong_before_ac` values match the history seen in plan 002.
3. **Rerun** `python -m app.sync` → incremental; it finishes in about 2 requests and changes nothing.
4. **Interrupt test:** Ctrl+C part-way through a `--full` run on a fresh DB, then rerun → it resumes and the final counts are the same.
5. **API:** start the app, `POST /api/sync`, then poll `GET /api/sync/status` until it succeeds.

## Outcome (implemented 2026-09-29)

Implemented as planned: migration `0002`; `app/sync/{solves,codehash,progress,engine,manager,__main__}.py`; `app/api/sync.py`; 18 new tests in `tests/sync/` (51 total), all offline.

**Live results on the real account:**

- **Backfill:** about 7 minutes, no retries or rate limiting. 97 problems (94 solved, 3 attempted), 416 submissions, 170 solves across 94 problems, and code for 192 submissions. `backfill_done = true`.
- **`longest-consecutive-sequence`** matches the history probed in plan 002 exactly: 15 submissions → 5 solves with `wrong_before_ac` = 1, 2, 1, 0, 0. Runtime-tweak accepts 3 minutes apart and a 16-hour follow-up were merged.
- **Rerun:** incremental, 2 requests (auth + 1 progress page), under 5 seconds, no changes.
- **API:** `POST /api/sync` → running; `GET /api/sync/status` → succeeded / incremental.
- **Not run live:** the Ctrl+C interrupt test (it would need another full backfill). Resume is covered by `test_interrupted_backfill_resumes`.

**Finding:** LeetCode's `numSubmitted` excludes **"Internal Error"** submissions (LeetCode's own failures), but the submission list includes them. `top-k-frequent-elements` has 12 counted vs 13 stored. This is harmless for change detection, since we compare stored vs remote `numSubmitted`, not row counts. However, an Internal Error would currently count as a wrong attempt. The only one here fell inside a merge window, so no solve was affected. **Resolved:** the engine now leaves `Internal Error` submissions out of solve grouping. They are stored, but they are not wrong attempts and their code is not fetched (`IGNORED_STATUSES` in `engine.py`, test `test_internal_errors_are_stored_but_not_wrong_attempts`).
