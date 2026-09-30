import { ChevronRight, Circle, PauseCircle, PlayCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { DifficultyText } from '@/components/difficulty-text'
import { FirstRun } from '@/components/first-run'
import { ProblemActionsMenu } from '@/components/problem-actions-menu'
import { LeetCodeLink, ProblemTitle } from '@/components/problem-links'
import { RatingButtons } from '@/components/rating-buttons'
import { RecallMeter } from '@/components/recall-meter'
import { RelativeTime } from '@/components/relative-time'
import { StudyModeToggle } from '@/components/study-mode-toggle'
import { TargetControl } from '@/components/target-control'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { problemCount, usePauseActions } from '@/hooks/use-pause-actions'
import type { AttemptedItem, DueItem, DueSection, PendingItem, StudyMode } from '@/lib/api'
import { useConfirmAll, useRateSolve, useToday } from '@/lib/queries'
import { cn } from '@/lib/utils'

export function TodayPage() {
  const { data: today, isPending, isError, error } = useToday()

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Today</h1>
        {today ? <TargetControl target={today.target} /> : null}
      </div>

      {isPending ? (
        <TodaySkeleton />
      ) : isError ? (
        <p className="text-sm text-destructive">Couldn't load Today: {error.message}</p>
      ) : !today.backfill_done ? (
        <FirstRun />
      ) : (
        <>
          <RateSection pending={today.pending} studyMode={today.study_mode} />
          <DueList due={today.due} />
          {today.attempted.length ? <AttemptedSection items={today.attempted} /> : null}
          {today.paused.length ? <PausedSection items={today.paused} /> : null}
        </>
      )}
    </div>
  )
}

function TodaySkeleton() {
  return (
    <>
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-64 w-full" />
    </>
  )
}

// --- Shared table styling -------------------------------------------------------------------
// Zebra rows with rounded ends (no dividers); actions muted until the row is hovered/focused.

const TABLE = 'table-fixed border-separate border-spacing-0'
const HEAD_ROW = 'border-0 hover:bg-transparent'
const HEAD = 'h-8 text-xs font-normal text-muted-foreground'
const ROW =
  'group border-0 hover:bg-muted/60 even:bg-muted/30 [&>td:first-child]:rounded-l-md [&>td:last-child]:rounded-r-md'
const ACTIONS =
  'text-muted-foreground group-hover:text-foreground group-focus-within:text-foreground max-sm:size-10'

// --- Rate your new solves -------------------------------------------------------------------

function RateSection({ pending, studyMode }: { pending: PendingItem[]; studyMode: StudyMode }) {
  const rateSolve = useRateSolve()
  const confirmAll = useConfirmAll()

  return (
    <Card>
      {/* Narrow cards: study mode drops below the title instead of squeezing it. */}
      <CardHeader className="@max-md/card-header:grid-cols-1">
        <CardTitle>Rate your new solves{pending.length ? ` (${pending.length})` : ''}</CardTitle>
        <CardAction className="@max-md/card-header:col-start-1 @max-md/card-header:row-start-2 @max-md/card-header:justify-self-start">
          <StudyModeToggle mode={studyMode} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {pending.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing to rate. Problems you solve on LeetCode show up here after the next sync.
          </p>
        ) : (
          <>
            <ul className="flex flex-col gap-4">
              {pending.map((item) => (
                <li key={item.solve_id} className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                    <span className="min-w-0 max-w-full">
                      <ProblemTitle
                        slug={item.slug}
                        title={item.title}
                        frontendId={item.frontend_id}
                      />
                    </span>
                    <DifficultyText difficulty={item.difficulty} />
                    <span className="text-muted-foreground">
                      solved <RelativeTime date={item.accepted_at} /> · {item.wrong_before_ac} wrong
                    </span>
                  </div>
                  <RatingButtons
                    selected={item.default}
                    disabled={rateSolve.isPending}
                    onSelect={(choice) =>
                      rateSolve.mutate(
                        { solveId: item.solve_id, choice },
                        { onError: (error) => toast.error(error.message) },
                      )
                    }
                  />
                </li>
              ))}
            </ul>
            {pending.length > 1 ? (
              <div>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={confirmAll.isPending}
                  onClick={() =>
                    confirmAll.mutate(
                      pending.map((p) => p.solve_id),
                      { onError: (error) => toast.error(error.message) },
                    )
                  }
                >
                  Confirm all as selected
                </Button>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  )
}

// --- Due for review ---------------------------------------------------------------------------
// Laid out by the card's width (container queries), not the window's, since the sidebar takes
// space. From 672px: header and columns, with Last solved from 768px. Narrower: two-line rows,
// with difficulty, recall, due and last solved under a title that may wrap.
// "Select" adds a checkbox column for pausing several problems at once.

const WIDE = 'hidden @2xl:table-cell'
const TITLE_WRAP = '@max-2xl:line-clamp-2 @max-2xl:whitespace-normal'

function DueList({ due }: { due: DueSection }) {
  const [showAll, setShowAll] = useState(false)
  const [selecting, setSelecting] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const { pauseProblems, pending } = usePauseActions()

  const targetMet = due.done_today >= due.target
  const visible = showAll ? due.items : due.items.slice(0, due.shown)
  const rolledOver = due.total_due - due.shown
  const visibleSlugs = visible.map((item) => item.slug)
  const selectedVisible = visibleSlugs.filter((slug) => selected.has(slug))
  const allSelected = visible.length > 0 && selectedVisible.length === visible.length

  const toggle = (slug: string, on: boolean) =>
    setSelected((current) => {
      const next = new Set(current)
      if (on) next.add(slug)
      else next.delete(slug)
      return next
    })
  const stopSelecting = () => {
    setSelecting(false)
    setSelected(new Set())
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Due for review</CardTitle>
        <CardDescription>
          {due.done_today} of {due.target} done today
          {targetMet ? ' · target met' : ''}
          {rolledOver > 0 ? ` · ${rolledOver} more due` : ''}
        </CardDescription>
        {due.total_due > 0 ? (
          <CardAction>
            <Button
              variant="ghost"
              size="sm"
              aria-pressed={selecting}
              onClick={() => (selecting ? stopSelecting() : setSelecting(true))}
            >
              {selecting ? 'Done' : 'Select'}
            </Button>
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent className="@container flex flex-col gap-2">
        {due.total_due === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing due. Nice.</p>
        ) : (
          <>
            {selecting ? (
              <div
                className="sticky top-2 z-10 flex flex-wrap items-center gap-2 rounded-md border bg-card px-3 py-2 text-sm shadow-sm"
                role="toolbar"
                aria-label="Selection"
              >
                <span className="text-muted-foreground">
                  {selectedVisible.length} selected
                </span>
                <Button
                  size="sm"
                  className="ml-auto"
                  disabled={selectedVisible.length === 0 || pending}
                  onClick={() =>
                    pauseProblems(selectedVisible, problemCount(selectedVisible.length), stopSelecting)
                  }
                >
                  <PauseCircle />
                  Pause selected ({selectedVisible.length})
                </Button>
                <Button variant="ghost" size="sm" onClick={stopSelecting}>
                  Cancel
                </Button>
              </div>
            ) : null}
            {visible.length ? (
              <Table className={TABLE}>
                <TableHeader className={selecting ? '' : 'hidden @2xl:table-header-group'}>
                  <TableRow className={HEAD_ROW}>
                    {selecting ? (
                      <TableHead className={`${HEAD} w-10`}>
                        <Checkbox
                          aria-label="Select all shown"
                          checked={allSelected ? true : selectedVisible.length ? 'indeterminate' : false}
                          onCheckedChange={(on) =>
                            setSelected(on === true ? new Set(visibleSlugs) : new Set())
                          }
                        />
                      </TableHead>
                    ) : null}
                    <TableHead className={HEAD}>
                      <span className={selecting ? '@max-2xl:sr-only' : ''}>Problem</span>
                    </TableHead>
                    <TableHead className={`${HEAD} ${WIDE} w-20`}>Difficulty</TableHead>
                    <TableHead className={`${HEAD} ${WIDE} w-28 text-right`}>Recall</TableHead>
                    <TableHead className={`${HEAD} ${WIDE} w-36 pl-6`}>Due</TableHead>
                    <TableHead className={`${HEAD} hidden w-32 @3xl:table-cell`}>
                      Last solved
                    </TableHead>
                    <TableHead className={`${HEAD} w-20 max-sm:w-24`}>
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visible.map((item) => (
                    <TableRow
                      key={item.slug}
                      className={ROW}
                      data-state={selected.has(item.slug) ? 'selected' : undefined}
                    >
                      {selecting ? (
                        <TableCell className="w-10">
                          <Checkbox
                            aria-label={`Select ${item.title}`}
                            checked={selected.has(item.slug)}
                            onCheckedChange={(on) => toggle(item.slug, on === true)}
                          />
                        </TableCell>
                      ) : null}
                      <TableCell className="whitespace-normal">
                        <ProblemTitle
                          slug={item.slug}
                          title={item.title}
                          frontendId={item.frontend_id}
                          className={TITLE_WRAP}
                        />
                        <p className="mt-0.5 text-xs text-muted-foreground @2xl:hidden">
                          <DifficultyText difficulty={item.difficulty} /> ·{' '}
                          {Math.round(item.recall * 100)}% recall · due{' '}
                          <RelativeTime date={item.due} />
                          {item.last_review ? (
                            <>
                              {' '}
                              · solved <RelativeTime date={item.last_review} />
                            </>
                          ) : null}
                        </p>
                      </TableCell>
                      <TableCell className={`${WIDE} w-20`}>
                        <DifficultyText difficulty={item.difficulty} />
                      </TableCell>
                      <TableCell className={`${WIDE} w-28`}>
                        <RecallMeter recall={item.recall} />
                      </TableCell>
                      <TableCell className={`${WIDE} w-36 pl-6 text-muted-foreground`}>
                        <RelativeTime date={item.due} />
                      </TableCell>
                      <TableCell className="hidden w-32 text-muted-foreground @3xl:table-cell">
                        {item.last_review ? <RelativeTime date={item.last_review} /> : '—'}
                      </TableCell>
                      <TableCell className="w-20 max-sm:w-24">
                        <div className="flex justify-end">
                          <LeetCodeLink slug={item.slug} title={item.title} className={ACTIONS} />
                          <ProblemActionsMenu
                            slug={item.slug}
                            title={item.title}
                            className={ACTIONS}
                          />
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : null}
            {rolledOver > 0 ? (
              <div>
                <Button variant="ghost" size="sm" onClick={() => setShowAll(!showAll)}>
                  {showAll ? 'Show fewer' : `Show ${rolledOver} more`}
                </Button>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  )
}

// --- Attempted, not yet solved ------------------------------------------------------------------
// Same container rules: columns from 672px (Last attempt from 768px, otherwise under the title).
// Narrower, difficulty and last result join the line under the title.

function AttemptedSection({ items }: { items: AttemptedItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Attempted, not yet solved ({items.length})</CardTitle>
      </CardHeader>
      <CardContent className="@container">
        <Table className={TABLE}>
          <TableHeader className="hidden @2xl:table-header-group">
            <TableRow className={HEAD_ROW}>
              <TableHead className={`${HEAD} w-8`}>
                <span className="sr-only">Status</span>
              </TableHead>
              <TableHead className={HEAD}>Problem</TableHead>
              <TableHead className={`${HEAD} w-20`}>Difficulty</TableHead>
              <TableHead className={`${HEAD} w-44`}>Last result</TableHead>
              <TableHead className={`${HEAD} hidden w-32 @3xl:table-cell`}>Last attempt</TableHead>
              <TableHead className={`${HEAD} w-12 max-sm:w-14`}>
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.slug} className={ROW}>
                <TableCell className="w-8 text-muted-foreground">
                  <Circle className="size-4" aria-label="Attempted" />
                </TableCell>
                <TableCell className="whitespace-normal">
                  <ProblemTitle
                    slug={item.slug}
                    title={item.title}
                    frontendId={item.frontend_id}
                    className={TITLE_WRAP}
                  />
                  <p className="mt-0.5 text-xs text-muted-foreground @3xl:hidden">
                    <span className="@2xl:hidden">
                      <DifficultyText difficulty={item.difficulty} />
                      {item.last_status ? ` · ${item.last_status}` : ''}
                      {item.last_submitted_at ? ' · ' : ''}
                    </span>
                    {item.last_submitted_at ? (
                      <>
                        last attempt <RelativeTime date={item.last_submitted_at} />
                      </>
                    ) : null}
                  </p>
                </TableCell>
                <TableCell className={`${WIDE} w-20`}>
                  <DifficultyText difficulty={item.difficulty} />
                </TableCell>
                <TableCell className={`${WIDE} w-44 truncate text-muted-foreground`}>
                  {item.last_status ?? '—'}
                </TableCell>
                <TableCell className="hidden w-32 text-muted-foreground @3xl:table-cell">
                  {item.last_submitted_at ? <RelativeTime date={item.last_submitted_at} /> : '—'}
                </TableCell>
                <TableCell className="w-12 max-sm:w-14">
                  <div className="flex justify-end">
                    <LeetCodeLink slug={item.slug} title={item.title} className={ACTIONS} />
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

// --- Paused ---------------------------------------------------------------------------------------
// Problems taken out of the review queue. Collapsed by default; a re-solve on LeetCode resumes
// a problem automatically, or resume it here.

function PausedSection({ items }: { items: DueItem[] }) {
  const [open, setOpen] = useState(false)
  const { resumeProblems, pending } = usePauseActions()

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <button
            type="button"
            className="flex items-center gap-1.5 hover:underline focus-visible:underline focus-visible:outline-none"
            aria-expanded={open}
            aria-controls="paused-list"
            onClick={() => setOpen(!open)}
          >
            <ChevronRight
              className={cn('size-4 transition-transform', open && 'rotate-90')}
              aria-hidden="true"
            />
            Paused ({items.length})
          </button>
        </CardTitle>
        <CardDescription>
          Not in your reviews. Solving one again on LeetCode resumes it automatically.
        </CardDescription>
        {open ? (
          <CardAction>
            <Button
              variant="ghost"
              size="sm"
              disabled={pending}
              onClick={() => resumeProblems({ all: true }, problemCount(items.length))}
            >
              Resume all
            </Button>
          </CardAction>
        ) : null}
      </CardHeader>
      {open ? (
        <CardContent id="paused-list" className="@container">
          <Table className={TABLE}>
            <TableHeader className="hidden @2xl:table-header-group">
              <TableRow className={HEAD_ROW}>
                <TableHead className={HEAD}>Problem</TableHead>
                <TableHead className={`${HEAD} w-20`}>Difficulty</TableHead>
                <TableHead className={`${HEAD} w-28 text-right`}>Recall</TableHead>
                <TableHead className={`${HEAD} hidden w-32 pl-6 @3xl:table-cell`}>
                  Last solved
                </TableHead>
                <TableHead className={`${HEAD} w-28`}>
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.slug} className={ROW}>
                  <TableCell className="whitespace-normal">
                    <ProblemTitle
                      slug={item.slug}
                      title={item.title}
                      frontendId={item.frontend_id}
                      className={TITLE_WRAP}
                    />
                    <p className="mt-0.5 text-xs text-muted-foreground @3xl:hidden">
                      <span className="@2xl:hidden">
                        <DifficultyText difficulty={item.difficulty} /> ·{' '}
                        {Math.round(item.recall * 100)}% recall
                        {item.last_review ? ' · ' : ''}
                      </span>
                      {item.last_review ? (
                        <>
                          solved <RelativeTime date={item.last_review} />
                        </>
                      ) : null}
                    </p>
                  </TableCell>
                  <TableCell className={`${WIDE} w-20`}>
                    <DifficultyText difficulty={item.difficulty} />
                  </TableCell>
                  <TableCell className={`${WIDE} w-28`}>
                    <RecallMeter recall={item.recall} />
                  </TableCell>
                  <TableCell className="hidden w-32 pl-6 text-muted-foreground @3xl:table-cell">
                    {item.last_review ? <RelativeTime date={item.last_review} /> : '—'}
                  </TableCell>
                  <TableCell className="w-28">
                    <div className="flex justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={pending}
                        className="text-muted-foreground group-hover:text-foreground group-focus-within:text-foreground"
                        aria-label={`Resume reviews for ${item.title}`}
                        onClick={() => resumeProblems({ slugs: [item.slug] }, item.title)}
                      >
                        <PlayCircle />
                        Resume
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      ) : null}
    </Card>
  )
}
