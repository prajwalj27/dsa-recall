import { ArrowDown, ArrowUp, ArrowUpDown, PauseCircle, PlayCircle, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { DifficultyText } from '@/components/difficulty-text'
import { LeetCodeLink, ProblemTitle } from '@/components/problem-links'
import { RecallMeter } from '@/components/recall-meter'
import { RelativeTime } from '@/components/relative-time'
import { SelectCell, SelectHead, SelectionBar } from '@/components/row-select'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useNow } from '@/hooks/use-now'
import { problemCount, usePauseActions } from '@/hooks/use-pause-actions'
import { useRowSelection } from '@/hooks/use-row-selection'
import type { Difficulty, SolvedRow } from '@/lib/api'
import { useSolved } from '@/lib/queries'
import {
  DEFAULT_FILTERS,
  DEFAULT_SORT,
  filterRows,
  type Filters,
  nextSort,
  type Sort,
  type SortKey,
  sortRows,
  type StatusFilter,
  tagCounts,
} from '@/lib/solved'
import { ACTIONS, HEAD, HEAD_ROW, ROW, TABLE, TITLE_WRAP, WIDE } from '@/lib/table-styles'
import { cn } from '@/lib/utils'

const STATUSES: { value: StatusFilter; label: string }[] = [
  { value: 'solved', label: 'Solved' },
  { value: 'due', label: 'Due' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'paused', label: 'Paused' },
  { value: 'unsolved', label: 'Unsolved' },
  { value: 'all', label: 'All' },
]
const DIFFICULTIES: { value: Difficulty | 'all'; label: string }[] = [
  { value: 'all', label: 'Any difficulty' },
  { value: 'Easy', label: 'Easy' },
  { value: 'Medium', label: 'Medium' },
  { value: 'Hard', label: 'Hard' },
]
const STATUS_LABEL: Record<SolvedRow['status'], string> = {
  due: 'Due',
  scheduled: 'Scheduled',
  paused: 'Paused',
  unsolved: 'Unsolved',
}
const ALL_TAGS = '__all__'
// Wider-card-only columns. Fixed widths are budgeted so Problem keeps >= ~200px at each
// breakpoint (the table always shows Problem and actions).
const WIDER = 'hidden @3xl:table-cell' // Last solved
const WIDEST = 'hidden @4xl:table-cell' // Recall
const TAGS = 'hidden @6xl:table-cell' // Tags: large screens only

export function SolvedPage() {
  const { data: rows, isPending, isError, error } = useSolved()
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [sort, setSort] = useState<Sort>(DEFAULT_SORT)

  const tags = useMemo(() => tagCounts(rows ?? []), [rows])
  const visible = useMemo(
    () => sortRows(filterRows(rows ?? [], filters), sort),
    [rows, filters, sort],
  )
  const filtered = JSON.stringify(filters) !== JSON.stringify(DEFAULT_FILTERS)

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Solved</h1>
        {rows ? (
          <p className="text-sm text-muted-foreground" aria-live="polite">
            Showing {visible.length} of {rows.length}
          </p>
        ) : null}
      </div>

      <FilterBar filters={filters} onChange={setFilters} tags={tags} />

      {isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : isError ? (
        <p className="text-sm text-destructive">Couldn't load your problems: {error.message}</p>
      ) : (
        <Card>
          <CardContent className="@container flex flex-col gap-2">
            {visible.length === 0 ? (
              <div className="flex flex-col items-start gap-2 py-6 text-sm text-muted-foreground">
                No problems match these filters.
                {filtered ? (
                  <Button variant="outline" size="sm" onClick={() => setFilters(DEFAULT_FILTERS)}>
                    Clear filters
                  </Button>
                ) : null}
              </div>
            ) : (
              <SolvedTable rows={visible} sort={sort} onSort={setSort} />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// --- Filters --------------------------------------------------------------------------------

function FilterBar({
  filters,
  onChange,
  tags,
}: {
  filters: Filters
  onChange: (filters: Filters) => void
  tags: { tag: string; count: number }[]
}) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch })
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            placeholder="Search by title or number"
            aria-label="Search problems"
            className="pl-8"
            value={filters.query}
            onChange={(event) => set({ query: event.target.value })}
          />
        </div>
        <Select
          value={filters.difficulty}
          onValueChange={(value) => set({ difficulty: value as Filters['difficulty'] })}
        >
          <SelectTrigger aria-label="Difficulty" className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DIFFICULTIES.map((d) => (
              <SelectItem key={d.value} value={d.value}>
                {d.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filters.tag ?? ALL_TAGS}
          onValueChange={(value) => set({ tag: value === ALL_TAGS ? null : value })}
        >
          <SelectTrigger aria-label="Tag" className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="max-h-80">
            <SelectItem value={ALL_TAGS}>All tags</SelectItem>
            {tags.map(({ tag, count }) => (
              <SelectItem key={tag} value={tag}>
                {tag} <span className="text-muted-foreground">({count})</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Status">
        {STATUSES.map((status) => (
          <Button
            key={status.value}
            size="sm"
            variant={filters.status === status.value ? 'secondary' : 'ghost'}
            aria-pressed={filters.status === status.value}
            onClick={() => set({ status: status.value })}
          >
            {status.label}
          </Button>
        ))}
      </div>
    </div>
  )
}

// --- Table ----------------------------------------------------------------------------------
// From 672px: Difficulty, Solves, Next review, Status; from 768px: Last solved; from 896px:
// Recall; from 1152px: Tags. Narrower: two-line rows. Hover checkboxes pause/resume several.

function SolvedTable({
  rows,
  sort,
  onSort,
}: {
  rows: SolvedRow[]
  sort: Sort
  onSort: (sort: Sort) => void
}) {
  const { pauseProblems, resumeProblems, pending } = usePauseActions()
  const selection = useRowSelection(rows.map((row) => row.slug))
  const selectedRows = rows.filter((row) => selection.isSelected(row.slug))
  const toPause = selectedRows.filter((row) => !row.paused).map((row) => row.slug)
  const toResume = selectedRows.filter((row) => row.paused).map((row) => row.slug)

  const head = (key: SortKey, label: string, className = '') => (
    <SortableHead sortKey={key} label={label} sort={sort} onSort={onSort} className={className} />
  )

  return (
    <>
      {selection.active ? (
        <SelectionBar count={selection.selected.length} onClear={selection.clear}>
          {toPause.length ? (
            <Button
              size="sm"
              disabled={pending}
              onClick={() => pauseProblems(toPause, problemCount(toPause.length), selection.clear)}
            >
              <PauseCircle />
              Pause ({toPause.length})
            </Button>
          ) : null}
          {toResume.length ? (
            <Button
              size="sm"
              variant={toPause.length ? 'outline' : 'default'}
              disabled={pending}
              onClick={() => {
                resumeProblems({ slugs: toResume }, problemCount(toResume.length))
                selection.clear()
              }}
            >
              <PlayCircle />
              Resume ({toResume.length})
            </Button>
          ) : null}
        </SelectionBar>
      ) : null}
      <Table className={TABLE}>
        <TableHeader className={selection.active ? '' : 'hidden @2xl:table-header-group'}>
          <TableRow className={HEAD_ROW}>
            <SelectHead
              className={HEAD}
              active={selection.active}
              allSelected={selection.allSelected}
              onSetAll={selection.setAll}
            />
            {head('number', 'Problem')}
            {head('difficulty', 'Difficulty', `${WIDE} w-20`)}
            <TableHead className={`${HEAD} ${TAGS} w-44`}>Tags</TableHead>
            {head('solves', 'Solves', `${WIDE} w-16`)}
            {head('last_solved', 'Last solved', `${WIDER} w-28`)}
            {head('next_review', 'Next review', `${WIDE} w-32`)}
            {head('recall', 'Recall', `${WIDEST} w-28`)}
            {head('status', 'Status', `${WIDE} w-22`)}
            <TableHead className={`${HEAD} w-12 max-sm:w-14`}>
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={row.slug}
              className={ROW}
              data-state={selection.isSelected(row.slug) ? 'selected' : undefined}
            >
              <SelectCell
                label={`Select ${row.title}`}
                checked={selection.isSelected(row.slug)}
                active={selection.active}
                onChange={(on) => selection.toggle(row.slug, on)}
              />
              <TableCell className="whitespace-normal">
                <ProblemTitle
                  slug={row.slug}
                  title={row.title}
                  frontendId={row.frontend_id}
                  className={TITLE_WRAP}
                />
                <p className="mt-0.5 text-xs text-muted-foreground @2xl:hidden">
                  <DifficultyText difficulty={row.difficulty} /> · {STATUS_LABEL[row.status]}
                  {row.next_review ? (
                    <>
                      {' '}
                      · <NextReview date={row.next_review} withPrefix />
                    </>
                  ) : null}
                  {' · '}
                  {row.solves} solve{row.solves === 1 ? '' : 's'}
                </p>
              </TableCell>
              <TableCell className={`${WIDE} w-20`}>
                <DifficultyText difficulty={row.difficulty} />
              </TableCell>
              <TableCell className={`${TAGS} w-44 truncate text-xs text-muted-foreground`}>
                <TagList tags={row.tags} />
              </TableCell>
              <TableCell className={`${WIDE} w-16 tabular-nums`}>{row.solves}</TableCell>
              <TableCell className={`${WIDER} w-28 text-muted-foreground`}>
                {row.last_solved ? <RelativeTime date={row.last_solved} /> : '—'}
              </TableCell>
              <TableCell className={`${WIDE} w-32`}>
                {row.next_review ? <NextReview date={row.next_review} /> : '—'}
              </TableCell>
              <TableCell className={`${WIDEST} w-28`}>
                {row.recall !== null ? <RecallMeter recall={row.recall} /> : null}
              </TableCell>
              <TableCell className={`${WIDE} w-22`}>
                <StatusText status={row.status} />
              </TableCell>
              <TableCell className="w-12 max-sm:w-14">
                <div className="flex justify-end">
                  <LeetCodeLink slug={row.slug} title={row.title} className={ACTIONS} />
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  )
}

function SortableHead({
  sortKey,
  label,
  sort,
  onSort,
  className,
}: {
  sortKey: SortKey
  label: string
  sort: Sort
  onSort: (sort: Sort) => void
  className?: string
}) {
  const active = sort.key === sortKey
  const Icon = !active ? ArrowUpDown : sort.dir === 'asc' ? ArrowUp : ArrowDown
  return (
    <TableHead
      className={cn(HEAD, className)}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button
        type="button"
        className={cn(
          'inline-flex items-center gap-1 hover:text-foreground focus-visible:text-foreground focus-visible:outline-none',
          active && 'text-foreground',
          sortKey === 'number' && '@max-2xl:sr-only',
        )}
        onClick={() => onSort(nextSort(sort, sortKey))}
      >
        {label}
        <Icon className={cn('size-3', !active && 'opacity-50')} aria-hidden="true" />
      </button>
    </TableHead>
  )
}

/** Next review as relative time; overdue ones in red. */
function NextReview({ date, withPrefix = false }: { date: string; withPrefix?: boolean }) {
  const now = useNow()
  const overdue = Date.parse(date) <= now.getTime()
  // withPrefix: "due 2 years ago" / "next in 3 months" (the narrow second line).
  const prefix = withPrefix ? (overdue ? 'due ' : 'next ') : null
  return (
    <span className={overdue ? 'text-hard' : 'text-muted-foreground'}>
      {prefix ?? (overdue ? <span className="sr-only">Overdue, due </span> : null)}
      <RelativeTime date={date} />
    </span>
  )
}

function StatusText({ status }: { status: SolvedRow['status'] }) {
  return (
    <span className={cn(status === 'due' ? 'font-medium text-hard' : 'text-muted-foreground')}>
      {STATUS_LABEL[status]}
    </span>
  )
}

function TagList({ tags }: { tags: string[] }) {
  if (!tags.length) return <>—</>
  const shown = tags.slice(0, 3)
  return (
    <span title={tags.join(', ')}>
      {shown.join(', ')}
      {tags.length > shown.length ? ` +${tags.length - shown.length}` : ''}
    </span>
  )
}
