import { describe, expect, it } from 'vitest'

import type { SolvedRow } from './api'
import { DEFAULT_FILTERS, filterRows, nextSort, sortRows, tagCounts } from './solved'

function row(overrides: Partial<SolvedRow>): SolvedRow {
  return {
    slug: 'x',
    title: 'X',
    difficulty: 'Medium',
    frontend_id: '1',
    tags: [],
    solves: 1,
    status: 'scheduled',
    paused: false,
    last_solved: '2026-01-01T00:00:00Z',
    next_review: '2026-12-01T00:00:00Z',
    recall: 0.9,
    last_activity: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

const ROWS: SolvedRow[] = [
  row({ slug: 'peak', title: 'Find Peak Element', frontend_id: '162', status: 'due', next_review: '2022-01-01T00:00:00Z', tags: ['Array', 'Binary Search'] }),
  row({ slug: 'mountain', title: 'Peak Index in a Mountain Array', frontend_id: '852', solves: 3, tags: ['Array'] }),
  row({ slug: 'split', title: 'Split Array Largest Sum', frontend_id: '410', difficulty: 'Hard', status: 'paused', paused: true, next_review: null, tags: ['Array', 'Dynamic Programming'] }),
  row({ slug: 'coins', title: 'Arranging Coins', frontend_id: '441', difficulty: 'Easy', status: 'unsolved', solves: 0, last_solved: null, next_review: null, recall: null, tags: ['Math'] }),
  row({ slug: 'coins-paused', title: 'Reverse Integer', frontend_id: '7', status: 'paused', paused: true, solves: 0, last_solved: null, next_review: null, recall: null }),
]

const slugs = (rows: SolvedRow[]) => rows.map((r) => r.slug)
const filter = (f: Partial<typeof DEFAULT_FILTERS>) => slugs(filterRows(ROWS, { ...DEFAULT_FILTERS, ...f }))

describe('filterRows', () => {
  it('defaults to solved problems, including paused solved but not paused attempted', () => {
    expect(filter({})).toEqual(['peak', 'mountain', 'split'])
  })

  it.each([
    ['due', ['peak']],
    ['scheduled', ['mountain']],
    ['paused', ['split', 'coins-paused']],
    ['unsolved', ['coins']],
    ['all', ['peak', 'mountain', 'split', 'coins', 'coins-paused']],
  ] as const)('status %s', (status, expected) => {
    expect(filter({ status })).toEqual(expected)
  })

  it('searches titles and numbers', () => {
    expect(filter({ query: 'peak' })).toEqual(['peak', 'mountain'])
    expect(filter({ query: '410' })).toEqual(['split'])
    expect(filter({ query: '410.' })).toEqual(['split'])
    expect(filter({ query: '  PEAK index ' })).toEqual(['mountain'])
  })

  it('filters by difficulty and tag', () => {
    expect(filter({ difficulty: 'Hard' })).toEqual(['split'])
    expect(filter({ tag: 'Binary Search' })).toEqual(['peak'])
    expect(filter({ status: 'all', tag: 'Math' })).toEqual(['coins'])
  })
})

describe('sortRows', () => {
  const sort = (key: Parameters<typeof nextSort>[1], dir: 'asc' | 'desc') => slugs(sortRows(ROWS, { key, dir }))

  it('sorts by next review with empties last in both directions', () => {
    expect(sort('next_review', 'asc')).toEqual(['peak', 'mountain', 'coins-paused', 'split', 'coins'])
    expect(sort('next_review', 'desc')).toEqual(['mountain', 'peak', 'coins-paused', 'split', 'coins'])
  })

  it('sorts by number, difficulty, solves, and status', () => {
    expect(sort('number', 'asc')).toEqual(['coins-paused', 'peak', 'split', 'coins', 'mountain'])
    expect(sort('difficulty', 'desc')[0]).toBe('split')
    expect(sort('solves', 'desc')[0]).toBe('mountain')
    expect(sort('status', 'asc')).toEqual(['peak', 'mountain', 'coins-paused', 'split', 'coins'])
  })

  it('sorts recall with unsolved last', () => {
    expect(sort('recall', 'asc').slice(-2)).toEqual(['coins-paused', 'coins'])
  })
})

describe('nextSort', () => {
  it('toggles the same column and starts new ones in a sensible direction', () => {
    expect(nextSort({ key: 'next_review', dir: 'asc' }, 'next_review')).toEqual({ key: 'next_review', dir: 'desc' })
    expect(nextSort({ key: 'next_review', dir: 'asc' }, 'solves')).toEqual({ key: 'solves', dir: 'desc' })
    expect(nextSort({ key: 'solves', dir: 'desc' }, 'number')).toEqual({ key: 'number', dir: 'asc' })
  })
})

describe('tagCounts', () => {
  it('counts tags, most common first', () => {
    expect(tagCounts(ROWS).slice(0, 2)).toEqual([
      { tag: 'Array', count: 3 },
      { tag: 'Binary Search', count: 1 },
    ])
  })
})
