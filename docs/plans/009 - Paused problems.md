# 009 — Paused problems

## Context

The user prepares specific problem sets (e.g. company-tagged lists) and doesn't want "Due for review" cluttered with older solved problems they aren't focusing on (72 due on the real account). They asked for a tag that takes a problem out of the recall queue until they either **solve it again** or **manually un-tag it**. The LLM pipeline is on hold; this is plan 009 (the LLM pipeline becomes 010).

The schema already supports this: `cards.suspended` exists (the design doc's "suspend removes a problem from reviews entirely", planned for step 5), and `due_reviews` already skips suspended cards. This plan adds the user-facing **Paused** state on top of it, plus the new rule that a re-solve resumes it automatically.

**Decisions made:**

- **Named "Paused":** actions "Pause reviews" and "Resume reviews". It reads as temporary.
- **Tag one at a time and in bulk:**
  - One at a time: the ⋯ menu on each due row, and a button in the problem panel.
  - Bulk: a "Select" mode on the due table (checkboxes, select all, "Pause selected (N)").
  - Filtered bulk actions ("pause all Easy", …) wait for the Solved page (build step 3).
- **Listed in a collapsed "Paused (N)" section** at the bottom of Today, with Resume per row and "Resume all".

## Behavior

- **Paused** means the problem is out of "Due for review", the due counts (sidebar badge, tab title), and `total_due`. Its history, ratings, and card are unchanged. FSRS recall keeps decaying (honest about memory), but nothing surfaces it.
- **Auto-resume:**
  - **A new solve** found by a sync (`rating_source` `inferred`, never `history`) resumes the card. It's scheduled from that fresh solve and appears under "Rate your new solves", so it returns *not* overdue.
  - **"Mark reviewed"** on a paused problem also resumes it (it's a re-solve done elsewhere).
- **Manual resume** returns the problem at its normal schedule. If it's overdue, it shows as due right away.
- **Bulk pause shows a toast with Undo**, which resumes exactly those problems.
- **Attempted-only problems** (no card) can't be paused: the action is hidden for them.
- **Later plans:** mastery and the skill tree (steps 3–4) should still count paused problems as knowledge, just not as review work. This will be noted in those plans.

## Changes

### Backend

- **DB:** reuse `cards.suspended` (no migration). The API and UI call it `paused`.
- **`app/engines/reviews`:**
  - `pause(session, slugs) -> int`, `resume(session, slugs) -> int`, `resume_all(session) -> int` (only slugs with a card; unknown ones are ignored).
  - `paused_problems(session, now)`: the same fields as `DueReview` (slug, title, difficulty, frontend_id, recall, due, last_review), most recently solved first.
  - `schedule_new_solves` resumes cards for slugs with new non-history solves. `mark_reviewed` resumes its card. `rebuild_card` already preserves `suspended`.
- **API:**
  - `POST /api/problems/pause {slugs: [...]}` and `POST /api/problems/resume {slugs: [...]}` or `{all: true}`, both returning `{changed: n}`.
  - `GET /api/today` gains `paused: [...]`.
  - `CardOut.suspended` is renamed to `paused`.
  - An empty slug list → 422.

### Frontend

- **`mark-reviewed-menu.tsx` → `problem-actions-menu.tsx`:** "Pause reviews" plus the existing "Mark reviewed as …" items.
- **Due table (`pages/today.tsx`):**
  - A "Select" toggle in the card header adds a checkbox column (header checkbox = select all visible rows, including after "Show more").
  - A sticky action bar with "Pause selected (N)" and "Cancel".
  - Selection is reset after pausing.
- **"Paused (N)" section:** collapsed by default. It has the same table styling (Problem, Difficulty, Recall, Last solved) with a Resume button per row, "Resume all", and the same responsive rules (container queries, two-line rows when narrow).
- **Problem panel:** when paused, the Review section shows a "Paused: not in your review queue. Solving it again resumes it." note and a Resume button; otherwise it shows a "Pause reviews" button.
- **Mutations** (`lib/queries.ts`: `usePause`, `useResume`) invalidate Today and the panel. The bulk-pause toast has an Undo action.
- **shadcn `checkbox`** is added via the CLI.

### Docs

- **Design doc (Spaced repetition → Overdue reviews):** "suspend removes a problem from reviews entirely" is replaced with the Paused behavior, including auto-resume on re-solve.
- On approval, this plan is copied to `docs/plans/009 - Paused problems.md`.

## Tests

- **Engine:**
  - pause/resume/resume_all counts, and unknown or card-less slugs are ignored.
  - `due_reviews` excludes paused cards.
  - A new inferred solve resumes; a history solve doesn't.
  - `mark_reviewed` resumes.
  - `paused_problems` ordering and fields.
  - A rebuild keeps paused.
- **Sync integration** (`FakeLeetCode`): pause after the backfill, then a new accepted submission → an incremental sync resumes it and it's pending a rating.
- **API:**
  - pause/resume/`all`, the `paused` list in Today, and `total_due` dropping.
  - `card.paused` in the problem detail.
  - 422 on an empty list.

## Verification

1. `pytest`, `ruff`, `tsc`, `oxlint`, `npm test`, and `npm run build` are clean.
2. **Dev DB** (per the saved rule: snapshot the dev `cards.suspended` state and settings first, restore them afterwards; prod checksummed before and after; a free 87xx port with the bind confirmed):
   - Scripted UI: Select mode → select 3 → "Pause selected (3)".
     - Due drops by 3, and "Paused (3)" appears.
     - Undo restores them.
     - Resume one → it's back in due.
     - Resume all.
   - Pausing from the ⋯ menu and from the panel both work.
   - Screenshots at 1280 px and 375 px: select mode, the paused section expanded, and the panel paused note.
3. **Auto-resume** is covered by the sync integration test (with no real new solve available on demand).

## Outcome (implemented 2026-09-30)

Implemented as planned.

- **Engine:** `pause` / `resume` / `resume_all` / `paused_problems` in `app/engines/reviews`, using the existing `cards.suspended` (no migration). Auto-resume happens in `schedule_new_solves` (non-history solves only) and in `mark_reviewed`.
- **API:** `POST /api/problems/pause` and `/resume` (`slugs` or `all`), `paused` in `GET /api/today`, and `card.paused` in the problem detail.
- **UI:**
  - `problem-actions-menu.tsx` (replaces `mark-reviewed-menu.tsx`).
  - `hooks/use-pause-actions.ts`: toasts, with Undo after pausing.
  - Select mode and the collapsible "Paused (N)" section in `pages/today.tsx`.
  - The Pause/Resume button and paused note in the problem panel.
  - The shadcn `checkbox`.
- **Design doc:** the suspend wording is replaced with Pause (auto-resume on re-solve).
- **Tests:** 134 backend (11 new: engine pause/resume, auto-resume on a new solve but not on history, mark reviewed resumes, sync integration, API routes and 422s) and 28 frontend. `ruff`, `tsc`, and `oxlint` are clean.

**Found in verification:** the row checkboxes built each new selection from the current render's state, so several toggles in the same tick kept only the last one. It's now a functional `setSelected` update.

**Verified on the dev DB** (:8777, bind confirmed; dev pause state, settings, and manual reviews snapshotted and matching afterwards; prod checksummed: unchanged). The UI was scripted:

- **Bulk:** Select → 3 rows → "Pause selected (3)", which took due from 85 to 82 with 3 paused. Undo put it back to 85 and 0.
- **One at a time:**
  - The ⋯ menu "Pause reviews" pauses that row.
  - The Paused section's Resume works per row, and "Resume all" works.
  - The problem panel's Pause and Resume both work, with the paused note shown.
- **Screenshots:** select mode, the Paused section, and the panel note at 1280 px. At 375 px, two-line rows with no horizontal scroll.
- **Auto-resume on a real re-solve** is covered by `test_solving_a_paused_problem_again_resumes_it` (sync integration).
