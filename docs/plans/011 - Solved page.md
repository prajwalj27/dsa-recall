# 011 — Solved page

## Context

Today only lists problems that need attention (due, to rate, attempted, paused). Once a problem is rated and scheduled, there's no way to find it again in the UI: to see when it's next due, look at its past solves, or re-rate it. The problem panel has all of that, but it's only reachable from Today's lists. The design doc plans a **Solved** page for build step 3 ("sortable, filterable table: problem, difficulty, skills, times solved, last solved, next review, status"). The user asked to build it now, before the LLM pipeline (which becomes plan 012).

**Decisions made:**

- **Rows:** every problem you've submitted to (solved and attempted). The status filter defaults to **Solved**.
- **No upcoming-reviews overview:** sorting by next review already shows what's coming.
- **History stays in the problem panel:** clicking a row's title opens it (full history and re-rating), as on Today.

## Design

### Columns

| Column | Content | Sortable |
| --- | --- | --- |
| Problem | "410. Split Array Largest Sum", opening the panel | yes (by number) |
| Difficulty | Easy / Med. / Hard colored text | yes (Easy → Hard) |
| Tags | LeetCode topic tags (up to 3 plus "+N"). The LLM "skills" replace them in a later plan. | no |
| Solves | Number of solves | yes |
| Last solved | Relative time | yes |
| Next review | "in 3 months", or "overdue · 2 years ago" in red; "—" for paused and unsolved | yes (default, soonest first) |
| Recall | The recall bar (solved only) | yes |
| Status | Due · Scheduled · Paused · Unsolved | yes |

- **Status:** Paused if paused; Unsolved if there's no card; Due if its next review has passed; otherwise Scheduled. "Mastered" arrives with the mastery score (build step 3).
- **Sorting:** clicking a header sorts by it, and clicking again reverses. Empty values (e.g. no next review) always sort last. Headers carry `aria-sort`.

### Filters

- **Search** by title or number.
- **Status chips:** Solved (default: Due + Scheduled + solved Paused) · Due · Scheduled · Paused · Unsolved · All.
- **Difficulty chips:** All · Easy · Medium · Hard.
- **Tag select:** "All tags" plus every tag, most common first.
- **Count:** "Showing 42 of 97". An empty result shows a clear-filters hint.

### Behavior

- **Bulk actions:** the same hover checkboxes. The selection bar offers **Pause** and/or **Resume**, depending on what's selected (each only affects problems where it applies). The Undo toast is the same as on Today.
- **Responsive:** container queries as on Today.
  - Full columns when wide.
  - Medium widths drop Tags and Recall.
  - Narrow cards use two-line rows: the title, then "Med. · Scheduled · next in 3 months · 2 solves".
- **Freshness:** the page shares the `today` / `problem` query invalidation, so re-rating in the panel updates the row's next review immediately.

## Changes

- **Backend:**
  - `app/engines/reviews`: `solved_list(session, now)` returns `ProblemRow` (slug, title, difficulty, frontend_id, tags, solves, last_solved, next_review, recall, status, paused). The rows are the problems with a `question_status`.
  - `GET /api/solved` → `list[SolvedRow]`.
- **Frontend:**
  - `lib/solved.ts`: pure filter and sort functions, unit tested with Vitest.
  - `pages/solved.tsx` replaces the placeholder route.
  - The table and the hover checkboxes reuse `row-select.tsx` and `use-row-selection.ts`.
  - `lib/queries.ts`: `useSolved`, invalidated with the review mutations.
- **Docs:** the design doc's Solved row notes "tags until skills exist".

## Tests

- **Backend:**
  - The status derivation for each case (due, scheduled, paused solved, paused attempted, unsolved).
  - The solves count, last solved, and next review.
  - Untouched problems are excluded.
  - The API shape.
- **Frontend (Vitest):**
  - Search by title and number.
  - The status, difficulty, and tag filters (the default Solved excludes unsolved).
  - Each sort key, direction, and empties last.

## Verification

1. `pytest`, `ruff`, `tsc`, `oxlint`, `npm test`, and `npm run build` are clean.
2. **Dev DB** (read-only except the bulk check, which touches only the rows it selects and restores them; the dev snapshot is compared afterwards; prod checksummed; a free 87xx port with the bind confirmed):
   - The default view lists solved problems sorted by next review.
   - Counts match the API.
   - Searching "peak" finds 162 and 852.
   - The Hard filter and a tag filter narrow the list.
   - Sorting by Solves (descending) puts the most-solved first.
   - A title click opens the panel.
   - Bulk pause, then Undo, restores it.
3. Screenshots at 1280 px, 800 px, and 375 px (the 375 px one uses an iframe and checks for no horizontal scroll).

## Outcome (implemented 2026-09-30)

Implemented as planned.

- **Backend:** `solved_list` and `ProblemRow` in `app/engines/reviews`; `GET /api/solved` (`app/api/solved.py`).
- **Frontend:**
  - `lib/solved.ts` (filter, sort, `nextSort`, `tagCounts`) and `pages/solved.tsx`, which replaces the placeholder route.
  - The table styles are shared between Today and Solved in `lib/table-styles.ts`.
  - `invalidateReviewData` refreshes Today, Solved, and the panel after any review change or sync.

**Fixed during verification:**

- **At 1280 px, every fixed-width column (≈910 px) left the Problem column no room.** The widths were trimmed and budgeted per breakpoint: Difficulty, Solves, Next review, and Status from 672 px; Last solved from 768 px; Recall from 896 px; Tags from 1152 px. The page container widened to `max-w-7xl`, so Tags show on large screens.
- **The narrow second line read "next 2 years ago" for overdue problems.** It now says "due 2 years ago" in red, and "next in 3 months" for upcoming ones.
- **Lint flagged `Date.now()` during render,** so `NextReview` uses `useNow()`, which also keeps the overdue color current.

**Tests:** 142 backend (4 new) and 41 frontend (13 new: filters, sorts, `nextSort`, `tagCounts`). `ruff`, `tsc`, and `oxlint` are clean.

**Verified on the dev DB** (:8781, bind confirmed; the dev snapshot matched afterwards; prod checksummed: unchanged). The UI was scripted:

- **Default view:** "Showing 94 of 97" (94 solved according to the API), soonest review first.
- **Filters:**
  - Search "peak" → 162 and 852.
  - Hard → 1 row, all Hard.
  - All → 97 of 97.
  - Unsolved → 7, 441, and 1497.
- **Sorting** by Solves → Group Anagrams first (`aria-sort` set).
- **A title click** opens the panel.
- **Bulk "Pause (2)"** took paused from 28 to 30, and Undo put it back to 28.

**Screenshots:** 1280 px (all columns but Tags), 1920 px (with Tags), 800 px and 375 px (two-line rows; 375 px has no horizontal scroll).
