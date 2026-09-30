# 005 — Today screen (build step 1, part 4)

## Context

Plans 002–004 built the pipeline: the LeetCode client, the sync, and the FSRS review engine. The real account now has 94 cards, 72 of them due. None of it is visible yet: the UI is still the skeleton from plan 001, and the engine is only usable through a CLI. This plan builds the first real screen, **Today** ("what to do now"), plus what it needs: API routes, the daily target, working sync controls, and a basic problem detail panel. It completes build step 1 of the design doc.

**Decisions made:**

- **Queue order: weighted priority.** `priority = (1 − recall) × weight`, with weights Easy 1, Medium 1.5, Hard 2 (the same weights as the design doc's mastery formula). Harder problems come first among equally forgotten cards, but a nearly forgotten Easy still beats a well-remembered Medium. On real data today the top of the queue is "Split Array Largest Sum" (Hard, 36%), then Mediums.
- **No history cleanup.** FSRS brings old problems back through the normal queue.
- **Durations are formatted in the frontend.** The API returns raw timestamps only (never "3 days ago" text). One frontend helper turns them into minutes, hours, days, months, or years using `Intl.RelativeTimeFormat`, with the exact date on hover. Labels stay current as time passes, without refetching.
- **Daily target modes now:** a compact control on Today. Casual (5), Steady (8, default), and Interview prep (15, retention 0.95, optional end date) set a default number that the user can adjust. Custom takes any number and a retention. The full Settings page stays in step 5.
- **Study mode switch** lives on Today, in the "Rate your new solves" header, with an optional end date.
- **Basic problem detail panel** is in scope; it's also where history can be re-rated.
- **Auto sync:** in the **built app** (`dsa-recall`), opening the app starts one incremental sync, and the Sync button runs one on demand. In **dev** (`npm run dev`) there is no auto sync, only the button, so hot reloads never hit LeetCode. The switch is `import.meta.env.PROD`, which Vite sets only in production builds.

## What Today shows

```
┌ Top bar ── [☰]                    Last synced 5 minutes ago  [⟳ Sync] ┐
│ Today                                  Daily target: [Steady ▾] [8]      │
├──────────────────────────────────────────────────────────────────────────┤
│ Rate your new solves (1)                 Study mode [off]  until [ date ] │
│   Car Fleet  Medium  solved 2 hours ago · 0 wrong                        │
│     [Again] [Hard] [Good●] [Easy] [Saw solution]                         │
├──────────────────────────────────────────────────────────────────────────┤
│ Due for review · 2 of 8 done today · 64 more due                          │
│   Split Array Largest Sum   Hard    recall 36%  due 4 years ago   ↗  ⋯   │
│   Subarray Product < K      Medium  recall 25%  due 4 years ago   ↗  ⋯   │
│   …                                                    [Show more]      │
├──────────────────────────────────────────────────────────────────────────┤
│ Attempted, not yet solved (3)                                            │
│   Median of Two Sorted Arrays  Hard  last: Time Limit Exceeded, 2 days ago ↗ │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Rate your new solves:** solves with `rating_source = inferred`. The default choice is pre-selected; clicking any of the five buttons saves it (and re-clicking the default confirms it). A "Confirm all" button accepts every default. Empty → the section collapses to one line.
- **Due for review:** `slots = max(target − done_today, 0)`. It shows the top `slots` due cards by priority. The header shows "X of N done today" and "M more due" (rolled over). "Show more" reveals the rest, since users can review beyond the target. When the target is met, the header says so and the list starts collapsed.
  - **`done_today`** counts reviews today of problems that already had a card, meaning re-solves and manual reviews. First solves don't count, per the design ("the target counts reviews only").
  - **"Today"** is the local day of the machine running the app. The app is local-first, so the server's clock *is* the user's clock.
- **Row actions:** clicking the title opens the detail panel, ↗ opens the problem on LeetCode, and ⋯ → "Mark reviewed" opens a rating picker (for re-solves done elsewhere). A problem re-solved on LeetCode leaves the due list at the next sync and shows up under "Rate your new solves".
- **Attempted, not yet solved:** problems with `question_status = ATTEMPTED` (never accepted), showing the last submission's status and time.
- **Suggested:** hidden until build step 3 (no placeholder).
- **First run** (`backfill_done` is false): Today shows a single progress card (phase, "37 / 97 problems", a bar) instead of the sections, driven by the sync status.
- **Due count everywhere:** a badge on Today in the sidebar and in the tab title, "(72) DSA Recall". A favicon badge and browser notifications come in step 5.

## Problem detail panel

A right-side sheet. It's opened by `?problem=<slug>` in the URL, so it works from any page and survives reloads. It shows:

- Title, difficulty, LeetCode topic tags, acceptance rate, "Open on LeetCode" (and "Premium" for paid-only problems)
- **Review status:** next review (relative time), recall %, reviews, lapses; a "Mark reviewed" button
- **Timeline** (newest first): each solve with its date, wrong attempts, and rating (`history`/`inferred`/`user`, plus "Saw solution"). The rating can be changed right there with the same five buttons, which is how to fix history. Under each solve are the submissions that led to it (status, language, runtime), and manual reviews appear as their own entries.
- Solution analysis (build step 2), and snooze/suspend (step 5), are not included yet.

## Backend

### Engine and settings changes

- **`app/engines/reviews`:**
  - `DIFFICULTY_WEIGHT = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.0}` (shared later with mastery)
  - `due_reviews` sorts by weighted priority (ties by slug) and returns `due` and `priority`; `days_overdue` is removed (the frontend formats from `due`)
  - `reviews_done_today(session, day_start)`
  - `problem_timeline(session, slug)`
- **`app/settings_store.py`:** target modes.
  - `get_target(session, today)` returns `mode`, `daily_target`, `retention`, and `interview_end_date`. If Interview prep's end date has passed, it switches back to `previous_mode` and saves that (lazily, on read).
  - `set_target(session, mode, daily_target=None, retention=None, end_date=None)` applies the mode defaults, remembers `previous_mode` when entering Interview prep, and calls `rebuild_all` when retention changes (instant for about 100 cards).

### API routes (Pydantic response models in `app/api/schemas.py`)

| Route | Purpose |
| --- | --- |
| `GET /api/today` | `pending` (solves to rate), `due` (items in priority order, `shown` count, `total_due`, `done_today`, `target`), `attempted`, `study_mode`, `target`, `backfill_done` |
| `GET /api/problems/{slug}` | Detail panel data: problem, card (+ recall), timeline |
| `POST /api/problems/{slug}/review` | `{choice}`: mark reviewed |
| `POST /api/solves/{id}/rating` | `{choice}`: rate or re-rate a solve |
| `POST /api/solves/confirm` | `{solve_ids}`: accept the defaults ("Confirm all") |
| `GET` / `PUT /api/settings/target` | Daily target mode, number, retention, end date |
| `PUT /api/settings/study-mode` | `{enabled, until}` |
| `POST /api/sync`, `GET /api/sync/status` | Existing (plan 003) |

All timestamps are ISO 8601 UTC. Unknown slug or solve → 404; invalid choice → 422.

## Frontend (`web/src/`)

| File | Responsibility |
| --- | --- |
| `lib/api.ts` | Typed request helpers and response types mirroring `app/api/schemas.py` |
| `lib/queries.ts` | TanStack Query hooks: `useToday`, `useProblem`, `useSyncStatus` (polls every 1 s only while running), `useStartSync`, `useRateSolve`, `useConfirmAll`, `useMarkReviewed`, `useTarget`, `useStudyMode`. Mutations invalidate `today` (and `problem`). |
| `lib/time.ts` | `relativeTime(date, now)` ("5 minutes ago", "in 3 days", "4 years ago") and `durationText(ms)` ("2 months"). Thresholds: < 1 min "just now", then minutes < 60, hours < 24, days < 30, months < 12, then years. |
| `hooks/use-now.ts` | Re-renders every minute so relative labels stay current |
| `components/relative-time.tsx` | `<RelativeTime date=… />` with the exact local date/time in a tooltip |
| `components/sync-control.tsx` | Top bar: "Last synced …", the Sync button, a progress label while running ("Syncing 12 / 97"). Error toasts by `error_kind`; `auth_expired` also shows a persistent banner ("LeetCode session expired: update LEETCODE_SESSION in .env and restart"). **Auto sync on mount only when `import.meta.env.PROD`**, guarded so React StrictMode can't fire it twice. |
| `components/first-run.tsx` | Full backfill progress card |
| `components/rating-buttons.tsx` | The five choices, with the default/current one highlighted |
| `components/difficulty-badge.tsx` | Easy/Medium/Hard badge (theme tokens) |
| `components/problem-panel.tsx` | The detail sheet, driven by `?problem=` |
| `components/target-control.tsx`, `study-mode-toggle.tsx` | The two Today header controls (a popover with the mode select, number input, and end date) |
| `pages/today.tsx` | The four sections above |
| `components/app-layout.tsx` | Mounts the sync control and panel; due badge; tab title |

New shadcn components as needed: `select`, `popover`, `switch`, `dropdown-menu`, `progress`, `calendar` (date picker), `alert`.

## Tests

- **Backend:**
  - Priority order (a Hard beats a Medium at equal recall; a low-recall Easy beats a high-recall Medium)
  - `done_today` excludes first solves and counts manual reviews
  - Target modes: defaults, adjusted number, interview expiry revert, and a retention change rebuilds cards
  - Each API route: happy path, 404, 422
  - Shared DB helpers (`add_problem`/`add_solve`) move from `tests/engines/test_reviews.py` to `tests/factories.py`
- **Frontend:** add **Vitest** for `lib/time.ts` (thresholds, past and future, singular and plural). Components are checked by build, lint, and a manual pass; there are no component tests yet.

## Verification

1. `pytest`, `ruff check .`, `npm run lint`, `npm run build`, and `npm test` are all clean.
2. **Production mode:** `npm run build --prefix web`, then `dsa-recall`.
   - Opening the page triggers exactly one sync (check the `/api/sync` calls in the server log).
   - Today shows 8 due, led by "Split Array Largest Sum"; the header shows "0 of 8 done today · 64 more due"; the tab title shows "(72) DSA Recall"; durations read like "4 years ago".
3. **Dev mode:** `npm run dev` plus uvicorn. No automatic `/api/sync` calls, including across hot reloads; the Sync button works.
4. **Interactions** (user in the browser, and I check through the API):
   - Switching to Interview prep sets retention to 0.95, and the due count rises.
   - Switching back restores it.
   - "Mark reviewed" on a due problem removes it from the list and bumps done_today.
   - Re-rating a past solve in the panel changes its next review.
   - Study mode on/off persists.
5. **Next real LeetCode solve:** after syncing, it appears under "Rate your new solves" with its default pre-selected.

## Outcome (implemented 2026-09-30)

Implemented as planned.

- **Backend:** weighted priority, `reviews_done_today`, `problem_timeline`, and `confirm_defaults` in `app/engines/reviews`; target modes in `app/settings_store.py` (`change_target`/`current_target` in the engine rebuild cards when retention changes); routes in `app/api/{today,problems,solves,settings,schemas,deps}.py`.
- **Frontend:** as in the file table, plus `lib/choices.ts` and `lib/sync.ts` (constants moved out of component files so hot reload keeps working). Dates use the native `<input type="date">` instead of a calendar library.
- **Tests:** 103 backend (30 new, including `tests/api/test_routes.py`; shared seeding helpers in `tests/factories.py`) and 28 Vitest cases for `lib/time.ts`. `ruff`, `oxlint`, and `tsc` are clean.

**Verified (headless Chrome against the built app, plus the API):**

- **Production mode:** one automatic `POST /api/sync` per page load. Today shows "0 of 8 done today · 64 more due", led by *Split Array Largest Sum* (Hard, 36%). The tab title is "(72) DSA Recall"; durations read "4 years ago" / "3 months ago".
- **Detail panel** (`?problem=longest-consecutive-sequence`): 5 solves with submissions grouped exactly as the solve grouping does, and the rating buttons are on each solve.
- **Phone width (375 px, measured in an iframe):** no horizontal overflow; recall and due columns hide below `sm`/`md`.
- **Dev mode:** sync state stays `idle` across page loads (no automatic syncs).
- **Interactions** (on a DB copy): Interview prep → retention 0.95, 85 due and 15 shown, and back again; mark reviewed → done 1, 71 due; re-rating a solve moves its next review; study mode persists.

**Incident during verification:** the user had their own `uvicorn --reload` running on :8000 against the real DB. My test server for the DB copy failed to bind to :8000, and my interaction checks went to the user's server. That wrote a manual review (split-array-largest-sum) and a re-rating (longest-consecutive-sequence solve #2) into the **real** DB, plus target-mode settings. My cleanup also killed that server's reloader process.

- **Reverted:** after a backup, the manual review was deleted and the solve restored to `history`/Hard, with both cards rebuilt. The state is back to 170 history reviews, 72 due, and `longest-consecutive-sequence` due 2027-01-19.
- **Left in place:** settings rows equal to the defaults (Steady, 8, 0.90), plus `previous_mode` and study mode off.
- Lesson recorded: check ports, confirm binds, and use a dedicated port for test servers.
