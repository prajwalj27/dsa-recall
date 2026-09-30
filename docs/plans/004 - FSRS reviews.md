# 004 — FSRS reviews (build step 1, part 3)

## Context

Plan 003 fills the database with the user's history as **solves** (170 on the real account, all unrated). This plan turns solves into spaced repetition: one FSRS card per solved problem, scheduled by replaying its reviews in date order, with ratings that are either inferred from wrong attempts or given by the user. It provides the engine functions the Today screen (plan 005) will call: due reviews, solves awaiting a rating, rate a solve, mark reviewed.

The design doc infers ratings from wrong attempts (3+ → Again, 1–2 → Hard, 0 → Good). The user raised a gap: when cramming before interviews, many people **read the solution first**, then pass on the first try. The inferred rating then says Good for a problem they couldn't solve alone. LeetCode gives no signal for this (no view or editorial timestamps), so this plan adds explicit ways for the user to say so.

**Decisions made:**

- **No learning steps and no fuzzing.** FSRS's default minute-level steps (1 m, 10 m) suit flashcards, not re-solving a problem. Previewed on real data: with the defaults, `rotting-oranges` sat in Learning, due 10 minutes after its solve. Without them, every interval is in days (e.g. `longest-consecutive-sequence`: 1d → 19d → 20d → 59d → 116d). Fuzzing is off so replays are deterministic.
- **History (solves loaded by the first backfill) uses the inferred rating silently:** 2 Again, 12 Hard, 156 Good. It never appears in "Rate your new solves". Any single solve can still be re-rated later (the engine supports it; the UI comes with the problem detail panel).
- **"Saw solution" rating option:** a fifth choice beside Again/Hard/Good/Easy. FSRS schedules it as **Again**, but it is stored as its own flag (`used_solution`), so mastery, insights, and suggestions can tell "learned from the solution" apart from "struggled".
- **Study mode toggle** (optional end date): "I'm learning from solutions right now". While it's on, **first-time** solves default to "Saw solution" instead of the inferred rating. **Re-solves are still inferred normally**, because a re-solve is the real memory test.

## Design

### Events and cards

- **`review_log` is the source of truth**: one row per solve (unique `solve_id`) plus manual "Mark reviewed" rows (`solve_id` NULL). Its `rating` is the effective FSRS rating.
- **`cards` is a cache**: `rebuild_card(slug)` replays that problem's `review_log` rows in `reviewed_at` order through the scheduler and writes the result: `due`, `stability`, `difficulty`, `state`, `last_review`, `reps` (number of reviews), and `lapses` (Again while in Review). `suspended` is preserved.
- **Changing a rating** means updating one `review_log` row and rebuilding one card (a handful of reviews, which is instant). There's no incremental state to get wrong.
- **Scheduler:** `Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False, desired_retention=R)`, where R comes from `settings` (default **0.90**, the design doc's Steady mode). Changing R later means `rebuild_all()`.

### Where a solve's rating comes from (`solves.rating_source`)

| `rating_source` | Meaning | Shown in "Rate your new solves" |
| --- | --- | --- |
| `history` | Found by the first backfill; inferred rating applied silently | No |
| `inferred` | Found by a later sync; a default is applied now so the card is scheduled right away, and the user can confirm or change it | Yes (default pre-selected) |
| `user` | The user chose the rating | No |

**Default for a new (`inferred`) solve:** if study mode is on (and not past its end date) *and* it's the problem's first solve, use "Saw solution" (rating Again, `used_solution = true`). Otherwise infer from `wrong_before_ac`.

### Sync hook

After the sync walk (whether it finished or stopped on a LeetCode error, since committed solves should still get cards), `schedule_new_solves()` runs in its own transaction. It finds solves with no `review_log` row, applies their default rating, inserts review rows, and rebuilds the affected cards. The sync engine marks solves as `history` when it runs in backfill mode before `backfill_done` was set. Solves found by a later `--full` resync are new, not history.

## Changes

### Migration `0003`

- `solves`: replace `rating_inferred` (bool) with `rating_source` (`history`/`inferred`/`user`), and add `used_solution` (bool, default false)
- `review_log`: unique index on `solve_id` (NULLs allowed for manual reviews)
- Data step: existing solves (all from the backfill) get `rating_source = 'history'`

### `app/engines/reviews.py`

| Function | Purpose |
| --- | --- |
| `make_scheduler(retention)` | The configured `Scheduler` |
| `infer_rating(wrong_before_ac)` | 3+ → Again, 1–2 → Hard, 0 → Good |
| `schedule_new_solves(session, now)` | The sync hook above; returns the count |
| `rebuild_card(session, slug)` / `rebuild_all(session)` | Replay review rows into `cards` |
| `set_rating(session, solve_id, choice)` | `choice` ∈ again/hard/good/easy/saw_solution; sets `rating_source = user`, updates `used_solution` and the review row, and rebuilds the card |
| `mark_reviewed(session, slug, choice, at)` | Manual review for a re-solve done elsewhere |
| `due_reviews(session, now, limit=None)` | Unsuspended cards with `due <= now`, **lowest recall first**, with recall %, days overdue, title, and difficulty |
| `pending_ratings(session)` | Solves with `rating_source = inferred`, newest first, with the pre-selected choice |
| `recall(card, now)` | Current retrievability, for the UI and later for mastery |

### `app/settings_store.py` (small)

Typed get/set over the `settings` table: `desired_retention` (default 0.90) and `study_mode` (`{enabled, until}`). The Settings page (plan 005+) will use it. Target modes and daily targets come with the Today screen.

### CLI: `python -m app.engines.reviews`

A way to use and check the engine before any UI exists:

- `due [--limit N]`: due reviews with recall % and days overdue
- `pending`: solves awaiting a rating
- `rate <solve_id> <again|hard|good|easy|saw>`
- `review <slug> <rating>`: manual mark-reviewed
- `study-mode on [--until YYYY-MM-DD]` / `study-mode off`
- `rebuild`: rebuild every card (after changing retention)

### Sync

`app/sync/engine.py`: sets `rating_source = history` when the solve is created during the initial backfill, and calls `schedule_new_solves` after the walk.

**Not in this plan:** API routes and the Today UI (plan 005), snooze, suspend UI, daily target modes, per-user FSRS parameter optimization (the design doc keeps `review_log` for this later), and mastery.

## Tests (`tests/engines/`)

- `infer_rating` boundaries (0, 1, 2, 3, 7)
- **Replay** matches calling `fsrs` directly for the same sequence; is deterministic across runs; counts `reps`/`lapses` correctly; and never schedules an interval under one day
- **`schedule_new_solves`:**
  - `history` solves get inferred ratings and never appear in `pending_ratings`
  - `inferred` solves appear in `pending_ratings`
  - It's idempotent: a second call does nothing
- **Study mode:**
  - A first solve defaults to Again with `used_solution`
  - A re-solve is inferred normally
  - After `until`, it's ignored
  - A `history` solve is unaffected
- **`set_rating`:**
  - Changing Good → Again moves `due` earlier, and only that card changes
  - `saw_solution` stores rating Again with `used_solution = true`
  - The solve is removed from `pending_ratings`
- **`mark_reviewed`** adds a review with no solve and pushes `due` out
- **`due_reviews`:** excludes cards that aren't due yet and suspended ones; orders by recall ascending; `limit` works
- **Sync integration** (reusing the plan 003 `FakeLeetCode`): a backfill creates one card per solved problem and none for attempted-only problems; a later incremental solve is `inferred` and pending
- **Migration `0003`** marks existing solves as `history`

## Verification

1. `pytest` and `ruff check .` are clean.
2. **On the real DB:** start the app or run `python -m app.sync`. The migration runs, then the hook schedules the 170 existing solves.
   - 94 cards (one per solved problem), 170 review rows, and 0 pending ratings.
   - `longest-consecutive-sequence` is due **2027-01-19**, matching the preview.
3. `python -m app.engines.reviews due --limit 10` shows a plausible lowest-recall-first list. Report the due count.
4. `rate <solve_id> saw` on one solve changes its due date and `used_solution`. Rating it back restores the original due date.
5. `study-mode on`, then a new first solve found by a later sync defaults to "Saw solution" (covered by tests; a live check happens naturally the next time you solve something new).

## Outcome (implemented 2026-09-30)

Implemented as planned: migration `0003`; `app/engines/reviews/` (engine in `__init__.py`, CLI in `__main__.py`); `app/settings_store.py`; `app/timeutil.py` (shared UTC helpers, moved out of the sync engine to avoid a circular import); and the sync hook. There are 21 new tests (73 total). The `session_factory` test fixture moved to `tests/conftest.py`.

- The migration uses a **named** unique index (`ux_review_log_solve_id`) rather than an unnamed unique constraint, so it can be downgraded. Up/down/up and `alembic check` are clean.
- `run_sync` now reports `succeeded` only after scheduling has finished. Scheduling also runs when the walk stops on a LeetCode error, so committed solves still get cards (tested).

**Live results on the real DB** (backed up before migrating):

- Sync → migration `0003` → 170 solves scheduled: **94 cards, 170 review rows, 0 pending**, and all solves `history`. Ratings are 2 Again, 12 Hard, 156 Good.
- `longest-consecutive-sequence`: due **2027-01-19**, 5 reps, 0 lapses, matching the preview.
- On a copy of the DB: `rate 6 saw` → next review 2026-09-28 with `used_solution = 1`; `rate 6 good` → back to 2027-01-19. `study-mode on --until 2026-10-15` works.

**Finding for plan 005 (Today screen):** **72 of 94 cards are due now**, and the lowest-recall end is dominated by Easy problems solved once around 2021 (e.g. "Running Sum of 1d Array", about 1,800 days overdue, 36% recall). This is FSRS working as designed: one Good review five years ago means low recall now. But a daily target filled with trivial Easies from years ago isn't useful. Options to decide in plan 005:

- A one-time "clean up old history" step: bulk-suspend, or mark as known, problems not touched in N years.
- Weight the queue so that, among long-idle cards, harder problems come first. The design doc already hints at this ("learned least firmly surface first").
- Show overdue durations humanely ("5 years ago") rather than "1827d overdue".
