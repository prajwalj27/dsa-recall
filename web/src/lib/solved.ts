/** Filtering and sorting for the Solved page (all in the browser; the list is small). */

import type { Difficulty, SolvedRow } from '@/lib/api'

export type StatusFilter = 'solved' | 'due' | 'scheduled' | 'paused' | 'unsolved' | 'all'
export type SortKey =
  | 'number'
  | 'difficulty'
  | 'solves'
  | 'last_solved'
  | 'next_review'
  | 'recall'
  | 'status'
export type Sort = { key: SortKey; dir: 'asc' | 'desc' }
export type Filters = {
  query: string
  status: StatusFilter
  difficulty: Difficulty | 'all'
  tag: string | null
}

export const DEFAULT_FILTERS: Filters = { query: '', status: 'solved', difficulty: 'all', tag: null }
export const DEFAULT_SORT: Sort = { key: 'next_review', dir: 'asc' }

function matchesStatus(row: SolvedRow, status: StatusFilter): boolean {
  if (status === 'all') return true
  if (status === 'solved') return row.solves > 0 // due, scheduled, and solved ones that are paused
  return row.status === status
}

function matchesQuery(row: SolvedRow, query: string): boolean {
  const q = query.trim().toLowerCase().replace(/\.$/, '')
  if (!q) return true
  const label = `${row.frontend_id ?? ''}. ${row.title}`.toLowerCase()
  return row.frontend_id === q || label.includes(q)
}

export function filterRows(rows: SolvedRow[], filters: Filters): SolvedRow[] {
  return rows.filter(
    (row) =>
      matchesStatus(row, filters.status) &&
      (filters.difficulty === 'all' || row.difficulty === filters.difficulty) &&
      (filters.tag === null || row.tags.includes(filters.tag)) &&
      matchesQuery(row, filters.query),
  )
}

const DIFFICULTY_ORDER: Record<Difficulty, number> = { Easy: 1, Medium: 2, Hard: 3 }
const STATUS_ORDER: Record<SolvedRow['status'], number> = {
  due: 1,
  scheduled: 2,
  paused: 3,
  unsolved: 4,
}

function sortValue(row: SolvedRow, key: SortKey): number | null {
  switch (key) {
    case 'number': {
      const n = Number.parseInt(row.frontend_id ?? '', 10)
      return Number.isNaN(n) ? null : n
    }
    case 'difficulty':
      return DIFFICULTY_ORDER[row.difficulty]
    case 'solves':
      return row.solves
    case 'last_solved':
      return row.last_solved ? Date.parse(row.last_solved) : null
    case 'next_review':
      return row.next_review ? Date.parse(row.next_review) : null
    case 'recall':
      return row.recall
    case 'status':
      return STATUS_ORDER[row.status]
  }
}

/** Sorts by `key`; empty values always go last, whichever the direction. Ties: by number. */
export function sortRows(rows: SolvedRow[], sort: Sort): SolvedRow[] {
  const factor = sort.dir === 'asc' ? 1 : -1
  const number = (row: SolvedRow) => sortValue(row, 'number') ?? Number.MAX_SAFE_INTEGER
  return [...rows].sort((a, b) => {
    const va = sortValue(a, sort.key)
    const vb = sortValue(b, sort.key)
    if (va === null && vb !== null) return 1
    if (vb === null && va !== null) return -1
    if (va !== null && vb !== null && va !== vb) return (va - vb) * factor
    return number(a) - number(b)
  })
}

/** Next sort after clicking a column header: toggle direction, or start a new column. */
export function nextSort(current: Sort, key: SortKey): Sort {
  if (current.key === key) return { key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
  // Counts and recall read best highest-first; dates and numbers soonest/lowest first.
  return { key, dir: key === 'solves' ? 'desc' : 'asc' }
}

/** Tags with how many problems have them, most common first. */
export function tagCounts(rows: SolvedRow[]): { tag: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const row of rows) for (const tag of row.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1)
  return [...counts]
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
}
