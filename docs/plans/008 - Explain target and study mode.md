# 008 — Explain the daily target and study mode

## Context

The user asked what separates study mode from the Casual / Steady / Interview prep / Custom modes. The Today screen explains neither well: study mode has only a hover `title` on its label, and the target popover has a one-line description per mode. The two controls are independent:

- **Target modes** set *how much and how soon* you review: the daily target number and the desired retention. Changing retention reschedules every card.
- **Study mode** sets *how a new first-time solve is rated*: it defaults to "Saw solution" instead of the rating inferred from wrong attempts. Re-solves are unaffected.

The user chose **short inline help**. On approval, save this as `docs/plans/008 - Explain target and study mode.md`. The LLM pipeline becomes plan 009.

## Changes (frontend only)

1. **New `components/help-popover.tsx`:** a small (?) icon button (`HelpCircle`, `aria-label="About …"`) that opens a `Popover` with a short explanation. It reuses the existing shadcn `Popover` (`components/ui/popover.tsx`). It works by keyboard (Enter/Space to open, Esc to close) and by touch, unlike the current hover-only `title`.
2. **`components/study-mode-toggle.tsx`:**
   - Replace the label's `title` attribute with a `HelpPopover` next to "Study mode". The text: *"Use this while learning from solutions. Problems you solve for the first time default to 'Saw solution', so they come back in about a day instead of being treated as solved on your own. Re-solves are still rated from your wrong attempts. It doesn't change your daily target or retention."*
   - When it's on, a one-line caption under the controls: *"New problems default to 'Saw solution'. Re-solves are rated normally."*
3. **`components/target-control.tsx`:**
   - A `HelpPopover` in the popover's header: *"Your daily target is how many due reviews Today shows; the rest roll over. Retention is how likely you should still remember a problem when it comes due: higher means reviews come sooner and more are due at once. Changing it reschedules every problem. Separate from study mode, which only affects how new problems are rated."*
   - Make each mode's description state the effect of its retention, e.g. Interview prep: *"About 15 reviews a day. 95% retention, so reviews come sooner and more are due. Optional end date."*
   - Keep the existing captions ("Only reviews count…", "Higher retention schedules reviews sooner…").

No backend or API changes.

## Verification

1. `npm run lint`, `npx tsc -b`, `npm test`, and `npm run build` are clean.
2. **Against the dev DB** (per plan 006: a free 87xx port with the bind confirmed; prod checksummed before and after, unchanged):
   - Screenshot Today at 1280 px with study mode off and on (toggled in dev): the caption appears only when it's on.
   - Screenshot each help popover open (it opens on click; open it via a headless keyboard focus + Enter script, or by rendering with the popover forced open).
   - 375 px iframe check: the (?) buttons and caption wrap without horizontal scroll.
3. Reset dev afterwards with `python -m app.db copy-prod-to-dev --yes`.

## Outcome (implemented 2026-09-30)

Implemented as planned:

- `help-popover.tsx` (a (?) button that opens an explanation; works by keyboard and touch)
- Study mode explanation, plus a caption while it's on
- Target popover explanation, and mode descriptions that state what their retention does

Two follow-ups came out of verification:

- **Phone header:** at narrow widths, the study mode controls squeezed "Rate your new solves" into a thin column. The Rate card header now stacks the controls under the title, left-aligned, below 448 px (a container query on the card header).
- **Dev data was not reset.** The dev DB held the user's own changes (Interview prep until 2026-10-10, previous mode Custom), so `copy-prod-to-dev` was skipped. Study mode, which I switched on in dev for the screenshots, was set back to off (its state when dev was copied from prod). Prod was checksummed before and after: unchanged.

**Verified** (dev DB, :8774, bind confirmed):

- Study mode help popover and caption at 1280 px.
- The target help popover opens inside the target popover (text shown, outer popover stays open).
- 375 px: header stacked, no horizontal scroll.
- `tsc`, `oxlint`, 28 Vitest tests, and the build are clean.

## Part 2 — Simplify target modes (requested 2026-09-30)
# 009 — Simplify target modes

### Context

The daily target has four modes (Casual, Steady, Interview prep, Custom), and changes apply the moment a field changes. Interview prep and study mode also have end dates with automatic switching back. The user wants something simpler and more deliberate:

- **Three modes: Casual, Steady, Interview.** Casual and Steady are fixed presets with no inputs. **Interview replaces Custom:** it's the one adjustable mode, with inputs for **reviews per day and retention**.
- **Nothing changes until "Apply"** is pressed in the target popover.
- **No end dates.** Remove "Interview prep ends" and study mode's "until". Users switch modes themselves.

### Behavior

| Mode | Reviews per day | Retention | Inputs |
| --- | --- | --- | --- |
| Casual | 5 | 90% | none: shown as text |
| Steady (default) | 8 | 90% | none: shown as text |
| Interview | default 15, adjustable 1–100 | default 95%, choose 80 / 85 / 90 / 95% | number and retention |

- **Target popover:** the draft is local. Changing the mode, number, or retention changes only the draft. **Apply** saves it (disabled when nothing changed or the number is invalid), and **Cancel**, or closing the popover, discards it.
  - Switching the draft to Interview pre-fills the saved Interview values if Interview was used before, else 15 / 95%.
  - A retention change reschedules every card on Apply, as today.
- **Study mode:** stays a single switch that applies immediately (it's a toggle, not a form). There's no date field; it's on until switched off.
- **Legacy data** (the user's dev DB currently has mode Interview with previous mode Custom and an end date): a stored mode of `custom` is read as `interview`, keeping its number and retention. The keys `interview_end_date`, `previous_mode`, and study mode `until` are ignored, and deleted on the next save.

### Changes

- **Backend:**
  - **`app/settings_store.py`:** `TARGET_MODES` is `casual` (5, 0.90), `steady` (8, 0.90), `interview` (defaults 15, 0.95). `Target` becomes `mode, daily_target, retention`.
    - `set_target` rejects a number or retention for Casual/Steady, and for Interview fills in the saved or default values.
    - The `custom` → `interview` mapping happens on read.
    - `revert_expired_interview` is removed; `StudyMode` becomes `enabled` only.
  - **`app/engines/reviews`:** `current_target` is simply `get_target`, with the expiry revert removed. `change_target` still rebuilds cards when retention changes.
  - **API:** `TargetIn { mode, daily_target?, retention? }`, `TargetOut { mode, daily_target, retention }`, `StudyModeIn/Out { enabled }`.
- **Frontend:**
  - `target-control.tsx`: the three-mode select, static text for Casual and Steady, inputs for Interview, and Apply / Cancel with a local draft.
  - `study-mode-toggle.tsx`: the date field and "(ended)" removed.
  - Help text and mode descriptions updated (no "Custom", no end dates).
  - `lib/api.ts`, `lib/queries.ts`: types match the API.
- **Docs:** the design doc's daily-target table is updated to the three modes, with no end date.

### Tests

- **Settings:**
  - The Casual and Steady presets; a number or retention given for them is rejected.
  - Interview defaults, custom values, and pre-filling from saved values.
  - A retention change rebuilds cards.
  - Legacy `custom` is read as `interview`, and legacy end-date and previous-mode keys are ignored and removed on save.
  - Study mode is enabled/disabled only.
- **API:** updated route tests for `/settings/target` and `/settings/study-mode`, with 422s for bad inputs.
- **Removed:** the interview-expiry and custom-mode tests.

### Verification

1. `pytest`, `ruff`, `tsc`, `oxlint`, `npm test`, and `npm run build` are clean.
2. **On the dev DB** (per the updated rule: record the current dev target and study mode first and restore them afterwards; prod checksummed before and after, unchanged; a free 87xx port with the bind confirmed):
   - The existing dev settings (Interview, previous Custom) load as Interview with their number and retention.
   - Screenshots of the popover for each mode: Casual and Steady show text only, Interview shows the inputs.
   - Changing the draft without Apply leaves the saved target unchanged (checked via `GET /api/settings/target`).
   - Apply saves it; Cancel discards it.
   - Study mode shows no date field.

### Outcome of Part 2 (implemented 2026-09-30)

Implemented as described.

- **Backend:**
  - `settings_store.py`: `PRESETS` (Casual 5/0.90, Steady 8/0.90) and Interview with saved `interview_target` / `interview_retention`. The legacy `custom` mode is read as `interview`, and the legacy `interview_end_date` / `previous_mode` keys are deleted on the next save. `StudyMode` is `enabled` only.
  - `current_target` and `revert_expired_interview` are removed. The API's `TargetOut` exposes the saved Interview values so the form can pre-fill them.
- **Frontend:** `target-control.tsx` edits a local draft with Apply / Cancel; `study-mode-toggle.tsx` has no date field. `DSA Recall - Design.md` is updated (three modes, no end dates, weighted priority).
- **Tests:** 123 backend (new: presets are fixed and reject values, Interview defaults / custom / remembered / partial update, legacy custom read as Interview, legacy keys removed, updated route tests and 422s) and 28 frontend. `ruff`, `tsc`, and `oxlint` are clean.

**Verified on the dev DB** (:8775, bind confirmed). The dev settings rows were snapshotted before and restored exactly afterwards, with cards rebuilt (85 due before and after). Prod was checksummed: unchanged.

- The user's legacy dev settings (Interview, previous mode Casual) load as Interview 15 / 95%.
- **Scripted UI checks:**
  - Editing the number enables Apply.
  - Cancel closes the popover (state `closed`) and leaves the saved target unchanged (15).
  - Apply saves it (20) and updates the button label.
- **Screenshots:** Interview shows both inputs; Steady shows only "8 reviews a day · 90% retention"; Apply is disabled until something changes.

**Follow-up: dropdown position.** Radix Select's default `position="item-aligned"` places the open list so the selected option sits over the trigger, so the list jumped up or down depending on the value. The shared `components/ui/select.tsx` now defaults to `position="popper"`, `side="bottom"`, `align="start"`, and `avoidCollisions={false}`. Every dropdown opens below its trigger, left-aligned and trigger-width, and never flips upward; with little room below, it shrinks and scrolls. Verified with Interview (the last option) selected: the list is 4 px below the trigger, left-aligned, with 3/3 options visible.
