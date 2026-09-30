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

## Part 2 — Hover checkboxes instead of a Select button (requested 2026-09-30)

### Context

The due table's bulk selection needed two clicks ("Select", then tick rows) and a button in the header. The user asked for checkboxes that appear when hovering a row, at its far left, with the first tick starting the same selection flow.

**Decisions made:**

- **Always show on touch:** devices without hover (`@media (hover: none)`) always show the checkboxes.
- **The Paused section gets the same pattern**, for bulk resume.

### Behavior

- **A checkbox column at the far left** of the due and paused tables. Its space is always reserved (so rows don't shift), and the checkbox is invisible until the row is hovered or the checkbox has keyboard focus. On touch devices it's always visible.
- **The first tick starts selection mode:**
  - Every row's checkbox stays visible.
  - The header shows a "select all" checkbox (for the rows currently shown).
  - An action bar appears: "N selected · Pause selected (N) · Clear" (the Paused section's bar says "Resume selected (N)").
  - Unticking the last box, Clear, or Esc ends selection mode.
- **The "Select" button is removed.** Undo after bulk pause is unchanged.

### Changes

- `hooks/use-row-selection.ts`: selected slugs (limited to the visible rows), toggle/set-all/clear, and Esc to clear.
- `components/row-select.tsx`: the header and row checkbox cells with the hover/focus/touch visibility rules.
- `pages/today.tsx`: `DueList` and `PausedSection` use them; the Select button is removed.

### Verification

- Scripted UI on the dev DB (snapshot and restore; prod checksummed):
  - Hovering a row reveals its checkbox (opacity changes).
  - Ticking a row shows the bar and all the checkboxes.
  - Pause selected, Undo, Esc clears.
  - Resume selected in the Paused section.
- Screenshots at 1280 px (hover state and selection mode) and 375 px (the checkboxes are shown on touch; the headless check uses a `hover: none` emulation note).

### Outcome of Part 2 (implemented 2026-09-30)

Implemented as described.

- **New:** `hooks/use-row-selection.ts` (selection limited to the visible rows, Esc clears) and `components/row-select.tsx` (`SelectHead`, `SelectCell`, `SelectionBar`).
- **Changed:** `DueList` and `PausedSection` in `pages/today.tsx` use them; the Select button is gone. The reveal rule is `opacity-0 group-hover:opacity-100 focus-visible:opacity-100 [@media(hover:none)]:opacity-100` until a selection starts, after which all the checkboxes stay visible.
- **Checks:** `tsc`, `oxlint`, 28 Vitest tests, and the build are clean; no backend changes.

**Verified on the dev DB** (:8778, bind confirmed; prod checksummed: unchanged). The UI was scripted:

- There's no Select button, and the row checkbox's opacity is 0 when idle and 1 with keyboard focus.
- Ticking one row shows the bar, makes the other checkboxes visible, and puts a select-all checkbox in the header. Esc clears it.
- "Pause selected (3)" took due from 85 to 82.
- In the Paused section, "Resume selected (2)" worked.
- Screenshot of selection mode at 1280 px.

**Not verified:** actual mouse hover and touch devices, since headless Chrome can't emulate `:hover` or `hover: none` from a page script. Both use the same class rules as the focus reveal, which was verified.

**Incident:** the test page started with "Resume all", which un-paused the 28 problems the user had paused in dev. The dev pause state was snapshotted beforehand and restored exactly (28 paused, matching the snapshot). The test rule now forbids "normalizing" dev state.

## Part 3 — Pause attempted problems too (implemented 2026-09-30)

**Request:** the "Attempted, not yet solved" rows get the same hover checkboxes, to move them into Paused.

**Decision:** a paused attempted problem resumes only when it's **solved**. Its first accepted submission turns it into a normal solved problem (card, "Rate your new solves"). Further failed attempts keep it paused.

**Also in this part:** the user removed "Pause reviews" from the ⋯ row menu. Pausing is now done with the row checkboxes and the problem panel. The leftovers (`showPause`, the unused imports) were cleaned up.

### Changes

- **Migration `0004`:** `problems.paused` replaces `cards.suspended`. Existing paused cards become paused problems, and the column is dropped from `cards`. Attempted problems have no card, so the flag had to move to the problem.
- **Engine:**
  - `pause` / `resume` / `resume_all` act on problems, so attempted-only problems count now.
  - `due_reviews` filters on `Problem.paused`.
  - `paused_problems` returns a `PausedProblem` (`solved`, plus recall and last solved, or last result and last attempt), most recent activity first.
  - Auto-resume is unchanged: a non-history solve, or "Mark reviewed".
- **API:** `GET /api/today`: `attempted` excludes paused problems, and `paused` is a `PausedItem` list. `paused` moved from `card` to `problem` in the problem detail.
- **UI:**
  - The Attempted table has hover checkboxes and "Pause selected (N)".
  - The Paused section shows attempted problems with ○ and their last result in place of the recall bar ("Recall / last result", "Last activity").
  - The problem panel's Pause/Resume works for any problem, with a note specific to attempted problems.
- **Design doc:** the data model (`problems.paused`) and the Pause description are updated.

### Tests

- 138 backend (new: attempted pause and its fields, a first solve resumes an attempted problem, a failed attempt keeps it paused (sync), migration 0004 copies the flags and drops the column, and the API's attempted/paused lists) and 28 frontend. `ruff`, `tsc`, and `oxlint` are clean.

### Verified on the dev DB

Test server on :8779, bind confirmed. The user's own servers on :8000/:5173 were left alone. The user's `--reload` server had already applied 0004 to dev, and the user's 28 paused problems carried over exactly (compared to the previous snapshot). Only `arranging-coins` was touched, and every step returned to 3 attempted / 28 paused:

- Its checkbox is invisible when idle. "Pause selected (1)" moved it into Paused as attempted, last result Wrong Answer. Undo put it back.
- Panel pause showed the attempted note; panel Resume worked.
- The Paused section's per-row Resume worked.
- Screenshot of the Paused section with the attempted row.

Dev matched its snapshot afterwards, and prod was checksummed: unchanged. **Prod is still on schema 0003.** It migrates to 0004, after an automatic backup to `data/backups/`, the next time `dsa-recall` starts.

**Follow-up:** the ○ status column was removed from "Attempted, not yet solved". Every row there is attempted, and next to the new checkbox it read like a second, broken checkbox. The ○ stays in the Paused section, where it marks attempted rows among solved ones.

**Follow-up:** in the Paused section, the ○ icon is also gone. The "Recall / last result" column is now **"Status"**: solved rows show their recall bar, and unsolved rows show **"Unsolved"** (also on the narrow-screen second line). The last result was dropped from this column; it's still in the problem panel. "Not attempted" was avoided because these problems *were* attempted, just never solved.
