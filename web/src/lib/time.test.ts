import { describe, expect, it } from 'vitest'

import { durationText, relativeTime } from './time'

const NOW = new Date('2026-09-30T12:00:00Z')
const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR

const ago = (ms: number) => new Date(NOW.getTime() - ms)
const ahead = (ms: number) => new Date(NOW.getTime() + ms)
const rel = (d: Date) => relativeTime(d, NOW, 'en-US')

describe('relativeTime', () => {
  it.each([
    [ago(20_000), 'just now'],
    [ahead(20_000), 'just now'],
    [ago(MIN), '1 minute ago'],
    [ago(59 * MIN), '59 minutes ago'],
    [ago(HOUR), '1 hour ago'],
    [ago(23 * HOUR), '23 hours ago'],
    [ago(DAY), 'yesterday'],
    [ago(12 * DAY), '12 days ago'],
    [ago(29 * DAY), '29 days ago'],
    [ago(30 * DAY), '1 month ago'],
    [ago(200 * DAY), '6 months ago'],
    [ago(364 * DAY), '12 months ago'],
    [ago(365 * DAY), '1 year ago'],
    [ago(1827 * DAY), '5 years ago'],
    [ago(1800 * DAY), '4 years ago'],
  ])('past: %s -> %s', (date, expected) => {
    expect(rel(date)).toBe(expected)
  })

  it.each([
    [ahead(5 * MIN), 'in 5 minutes'],
    [ahead(DAY), 'tomorrow'],
    [ahead(3 * DAY), 'in 3 days'],
    [ahead(111 * DAY), 'in 3 months'],
    [ahead(800 * DAY), 'in 2 years'],
  ])('future: %s -> %s', (date, expected) => {
    expect(rel(date)).toBe(expected)
  })

  it('accepts ISO strings', () => {
    expect(relativeTime('2026-09-27T12:00:00Z', NOW, 'en-US')).toBe('3 days ago')
  })
})

describe('durationText', () => {
  it.each([
    [10_000, 'less than a minute'],
    [MIN, '1 minute'],
    [2 * HOUR, '2 hours'],
    [12 * DAY, '12 days'],
    [65 * DAY, '2 months'],
    [4 * 365 * DAY, '4 years'],
    [-12 * DAY, '12 days'],
  ])('%s ms -> %s', (ms, expected) => {
    expect(durationText(ms, 'en-US')).toBe(expected)
  })
})
