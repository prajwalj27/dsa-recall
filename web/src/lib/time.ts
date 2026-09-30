/**
 * Human-readable durations. The API only sends ISO timestamps; all wording lives here.
 *
 * Units are chosen by size: < 1 min "just now", then minutes (< 60), hours (< 24),
 * days (< 30), months (< 12), years. Counts are floored, so 1,800 days is "4 years".
 */

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const MONTH = 30 * DAY
const YEAR = 365 * DAY

type Unit = 'year' | 'month' | 'day' | 'hour' | 'minute'

const UNITS: [Unit, number][] = [
  ['year', YEAR],
  ['month', MONTH],
  ['day', DAY],
  ['hour', HOUR],
  ['minute', MINUTE],
]

function pickUnit(absMs: number): [Unit, number] {
  for (const [unit, size] of UNITS) {
    if (absMs >= size) return [unit, Math.floor(absMs / size)]
  }
  return ['minute', 0]
}

export function toDate(value: Date | string): Date {
  return value instanceof Date ? value : new Date(value)
}

/** "just now", "5 minutes ago", "yesterday", "in 3 days", "4 years ago". */
export function relativeTime(value: Date | string, now: Date = new Date(), locale?: string): string {
  const diff = toDate(value).getTime() - now.getTime()
  const abs = Math.abs(diff)
  if (abs < MINUTE) return 'just now'
  const [unit, count] = pickUnit(abs)
  // "yesterday"/"tomorrow" read well; "last year" is ambiguous, so only days use words.
  const format = new Intl.RelativeTimeFormat(locale, { numeric: unit === 'day' ? 'auto' : 'always' })
  return format.format(diff < 0 ? -count : count, unit)
}

/** A length of time without direction: "12 days", "2 months", "4 years". */
export function durationText(ms: number, locale?: string): string {
  const abs = Math.abs(ms)
  if (abs < MINUTE) return 'less than a minute'
  const [unit, count] = pickUnit(abs)
  return new Intl.NumberFormat(locale, { style: 'unit', unit, unitDisplay: 'long' }).format(count)
}

/** The exact local date and time, for tooltips. */
export function exactTime(value: Date | string, locale?: string): string {
  return toDate(value).toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' })
}
