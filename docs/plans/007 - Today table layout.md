# 007 — Today table layout

## Context

The Today lists (plan 005) are rows of inline text with labels repeated in every row ("recall 36%", "due 4 years ago"), and difficulty badges that land at different positions depending on title length. The user asked for a table with a header row (Problem, Difficulty, Recall, Due, and a new Last solved column), styled after LeetCode's problem list: zebra rows, "1. Two Sum" numbering, and difficulty as colored text. The tool is meant for desktop, but the user wants a properly responsive site. The LLM pipeline moves to plan 008.

**Decisions made:**

- **A real table** (shadcn `Table`, semantic `<table>`) with a **quiet header row**: small muted labels. Screen readers then announce each cell with its column name.
- **Borrowed from LeetCode's list:**
  - Zebra rows with rounded corners instead of dividers
  - `frontend_id` numbering ("410. Split Array Largest Sum")
  - Difficulty as colored text (**Easy / Med. / Hard**) rather than outlined badges, also in the problem panel for consistency
  - Right-aligned number columns
  - An open-circle status icon for "Attempted, not yet solved"
- **Recall shown as a short bar plus %**, where LeetCode puts its frequency bar. It's colored by recall (< 50% red, < 75% amber, else green, using theme tokens), and the number is always shown, so the color is never the only signal.
- **Last solved** = the card's last review, meaning the latest re-solve or manual "Mark reviewed".
- **Row order stays the priority queue.** Columns aren't sortable on Today, because re-sorting would conflict with which problems the daily target shows. Sorting belongs to the Solved page (build step 3).
- **Actions** (↗ LeetCode, ⋯ Mark reviewed) are always visible, muted, and brighten when you hover or focus the row. They're never hover-only, which hurts discoverability and doesn't work on touch.
- **Original styling:** the same pattern as LeetCode's list, but with our own tokens and fonts. No copied assets.

## Layout by width (desktop first)

| Width | Due table | Attempted table |
| --- | --- | --- |
| **≥ 1024 px** (desktop) | ○ · Problem · Difficulty · Recall (bar + %) · Due · Last solved · actions | ○ · Problem · Difficulty · Last result · Last attempt · ↗ |
| **640–1023 px** (tablet, narrow window) | Last solved is dropped; the rest stays | Last attempt is shown under the title |
| **< 640 px** (phone) | No header row. Each row is two lines: "410. Title · Hard" on top, and "36% recall · due 4 years ago · solved 4 years ago" underneath. The actions stay on the right. | Same two-line pattern |

- **Reflow, not hide:** narrow screens move secondary values onto the second line, so nothing is lost on a phone.
- **Touch targets:** the icon buttons grow to 40 px below 640 px.
- **Long titles** truncate with an ellipsis (the full title is in the tooltip) and never force the page wider than the screen.
- **Rest of Today at phone width:**
  - The top bar keeps Sync and drops the "Last synced" text (already the case).
  - The daily target button shortens to "8/day".
  - The rating buttons wrap.
  - The problem panel goes full width.

## Changes

- **Backend:** `DueItem` gains `frontend_id` and `last_review`; `AttemptedItem` gains `frontend_id`; `PendingItem` gains `frontend_id`. They're filled in `app/engines/reviews` (`due_reviews`, `pending_ratings`) and `app/api/today.py`. The existing route tests are updated to check the new fields.
- **Frontend:**
  - `components/difficulty-text.tsx` replaces `difficulty-badge.tsx` (Easy/Med./Hard colored text, with full names for screen readers).
  - `components/recall-meter.tsx`: a bar plus %, `role="meter"` with `aria-valuenow`.
  - `ProblemTitle` shows the `frontend_id` prefix.
  - `pages/today.tsx`: `DueList` and `AttemptedSection` rebuilt as tables with the responsive rules above. "Rate your new solves" keeps its card layout (it's a form, not a table) but uses the new numbering and difficulty text.
  - `target-control.tsx`: short label below 640 px.
  - Zebra rows via `even:bg-muted/40`-style classes on theme tokens (works in light and dark).

## Verification

1. `pytest`, `ruff`, `npm run lint`, `npm test`, and `npm run build` are clean.
2. **Against the dev database** (per plan 006; prod files checksummed before and after, unchanged), screenshots of the built app at **1280 px, 800 px, and 375 px** (375 px via the iframe method, since headless Chrome's minimum window is 504 px):
   - The header shows at ≥ 640 px, and zebra rows alternate.
   - "410. Split Array Largest Sum" is first, with "Hard" in red text.
   - The recall bar is colored and the % is visible.
   - Last solved appears at ≥ 1024 px.
   - At 375 px: two-line rows, no horizontal scroll (`scrollWidth == clientWidth`), and the actions are reachable.
3. The problem panel uses the new difficulty text.
4. **Keyboard:** Tab reaches every title, ↗, and ⋯ in row order, with visible focus.

## Outcome (implemented 2026-09-30)

Implemented as planned, with one deliberate change:

- **Container queries instead of window breakpoints.** The first build switched layouts by window width. At an 800 px window, the 256 px sidebar left the card only about 470 px wide while the "tablet" layout still kept every column, so titles were crushed to "410. S…". The tables now lay out by the **card's own width** (Tailwind v4 `@container`):
  - From 672 px: header row and columns.
  - From 768 px: Last solved / Last attempt columns.
  - Narrower: two-line rows. The title may wrap to 2 lines, with difficulty, recall, due, and last solved underneath.
  - The result: an 800 px window gets readable two-line rows, and a 1280 px window gets the full table.
- **Phone:** difficulty moved from its own column onto the second line, which gives the title the full width. The daily target button shows "8/day" below 640 px.

**Files:**

- New: `difficulty-text.tsx` (replaces `difficulty-badge.tsx`, also used in the problem panel) and `recall-meter.tsx` (`role="meter"`).
- `ProblemTitle` takes a `frontendId` and a `className`.
- `DueItem` gained `frontend_id` and `last_review`; `PendingItem` and `AttemptedItem` gained `frontend_id`.

**Verified on the dev DB** (server on :8773, bind confirmed; prod checksummed before and after, unchanged):

- **1280 px:** full table. Header; zebra rows; "410. Split Array Largest Sum" first with "Hard" in red; colored recall bars; Last solved; a gap between Recall and Due.
- **800 px:** two-line rows with full titles.
- **375 px** (iframe): `scrollWidth == clientWidth == 375`; titles wrap to 2 lines; "8/day".
- **Problem panel:** "Hard" as colored text.
- **Tests:** 118 backend and 28 frontend pass; `tsc` and `oxlint` are clean.
- **Keyboard order** follows DOM order (title → ↗ → ⋯ per row, all native buttons and links). Not exercised interactively.
