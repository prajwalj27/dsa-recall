# 010 — Rating order and colors

## Context

The five rating choices appear in three places: "Rate your new solves" on Today, the timeline in the problem panel, and the "Mark reviewed as" menu. They were ordered Again · Hard · Good · Easy · Saw solution and looked identical, so the weakest outcome (Saw solution) sat at the end and nothing signaled which choice meant what. The user wants them reordered and color-coded, so rating by how well you knew a problem is quick. The LLM pipeline moves to plan 011.

**Decisions made:**

- **Order worst → best:** Saw solution · Again · Hard · Good · Easy. It reads as a scale, and Saw solution sits next to Again, which it's scheduled like.
- **Distinct colors:** Saw solution purple, Again red, Hard orange, Good green, Easy blue.

## Design

- **Separate theme tokens** `--rate-saw`, `--rate-again`, `--rate-hard`, `--rate-good`, `--rate-easy`, each with light and dark values, exposed as Tailwind colors (`text-rate-good`, `bg-rate-good`, …). Kept separate from the problem-difficulty colors (Easy/Medium/Hard), so "rated Easy" is never confused with "an Easy problem".
- **Color is a second cue only:** the label and position carry the meaning (color-blind safe), and the hover hints stay.
- **Rating buttons:**
  - Unselected: an outline with the rating's color on the text and a tinted border, plus a faint tinted hover.
  - Selected: filled with the rating's color, with high-contrast text (the page background color), plus `aria-pressed`.
- **"Mark reviewed as" menu:** the same order, each item with a small colored dot.
- **One source of truth:** `lib/choices.ts` holds the order, labels, hints, and a static class map per choice (Tailwind can't see dynamically built class names).

## Changes

- `web/src/index.css`: the five tokens (light and dark) and their `@theme` mappings.
- `web/src/lib/choices.ts`: the new order, plus a `tone` class map.
- `web/src/components/rating-buttons.tsx`: colored styles.
- `web/src/components/problem-actions-menu.tsx`: colored dots.

## Verification

- `tsc`, `oxlint`, `npm test`, and `npm run build` are clean.
- Screenshots (dev DB, read-only views; prod checksummed): the problem panel timeline with colored rating rows, and the "Mark reviewed as" menu open. "Rate your new solves" uses the same component.

## Outcome (implemented 2026-09-30)

Implemented as planned, with two fixes found in the screenshots:

- **The selected button was unreadable in dark mode:** the outline variant's `dark:bg-input/30` outranked the rating fill. The selected button now uses the solid `default` variant, and `cn` (tailwind-merge) swaps its `bg-primary` for the rating color. Unselected buttons also get `dark:border-rate-*` / `dark:hover:bg-rate-*`, so the tint shows in dark mode.
- **The panel wrapped the fifth button:** `RatingButtons` takes `size` (`sm` by default); the problem panel uses `xs`, so all five fit on one line. Today's "Rate your new solves" keeps `sm`.

**Verified** (dev DB, read-only views on :8780, bind confirmed; prod checksummed: unchanged):

- **Panel:** Saw solution · Again · Hard · Good · Easy in purple / red / orange / green / blue, with the selected rating filled.
- **"Mark reviewed as" menu:** the same order with colored dots.
- `tsc`, `oxlint`, and the build are clean; no backend changes.
