/**
 * Shared styling for the problem tables (Today, Solved): zebra rows with rounded ends and no
 * dividers; actions muted until the row is hovered or focused. Layout follows the card's width
 * (container queries), not the window's, since the sidebar takes space.
 */

export const TABLE = 'table-fixed border-separate border-spacing-0'
export const HEAD_ROW = 'border-0 hover:bg-transparent'
export const HEAD = 'h-8 text-xs font-normal text-muted-foreground'
export const ROW =
  'group border-0 hover:bg-muted/60 even:bg-muted/30 [&>td:first-child]:rounded-l-md [&>td:last-child]:rounded-r-md'
export const ACTIONS =
  'text-muted-foreground group-hover:text-foreground group-focus-within:text-foreground max-sm:size-10'

/** Columns shown once the card is at least 672px wide; narrower cards use two-line rows. */
export const WIDE = 'hidden @2xl:table-cell'
/** Titles may wrap to two lines in narrow cards, and truncate in wide ones. */
export const TITLE_WRAP = '@max-2xl:line-clamp-2 @max-2xl:whitespace-normal'
