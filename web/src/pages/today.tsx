import { useState } from 'react'
import { toast } from 'sonner'

import { DifficultyBadge } from '@/components/difficulty-badge'
import { FirstRun } from '@/components/first-run'
import { MarkReviewedMenu } from '@/components/mark-reviewed-menu'
import { LeetCodeLink, ProblemTitle } from '@/components/problem-links'
import { RatingButtons } from '@/components/rating-buttons'
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
import { Skeleton } from '@/components/ui/skeleton'
import type { AttemptedItem, DueSection, PendingItem, StudyMode } from '@/lib/api'
import { useConfirmAll, useRateSolve, useToday } from '@/lib/queries'

export function TodayPage() {
  const { data: today, isPending, isError, error } = useToday()

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
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

// --- Rate your new solves -------------------------------------------------------------------

function RateSection({ pending, studyMode }: { pending: PendingItem[]; studyMode: StudyMode }) {
  const rateSolve = useRateSolve()
  const confirmAll = useConfirmAll()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rate your new solves{pending.length ? ` (${pending.length})` : ''}</CardTitle>
        <CardAction>
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
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
                    <ProblemTitle slug={item.slug} title={item.title} />
                    <DifficultyBadge difficulty={item.difficulty} />
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

function DueList({ due }: { due: DueSection }) {
  const [showAll, setShowAll] = useState(false)
  const targetMet = due.done_today >= due.target
  const visible = showAll ? due.items : due.items.slice(0, due.shown)
  const rolledOver = due.total_due - due.shown

  return (
    <Card>
      <CardHeader>
        <CardTitle>Due for review</CardTitle>
        <CardDescription>
          {due.done_today} of {due.target} done today
          {targetMet ? ' · target met' : ''}
          {rolledOver > 0 ? ` · ${rolledOver} more due` : ''}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {due.total_due === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing due. Nice.</p>
        ) : (
          <>
            {visible.length ? (
              <ul className="flex flex-col divide-y">
                {visible.map((item) => (
                  <li key={item.slug} className="flex items-center gap-2 py-2 text-sm">
                    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
                      <ProblemTitle slug={item.slug} title={item.title} />
                      <DifficultyBadge difficulty={item.difficulty} />
                    </div>
                    <span className="hidden w-20 text-right text-muted-foreground sm:inline">
                      recall {Math.round(item.recall * 100)}%
                    </span>
                    <span className="hidden w-36 text-right text-muted-foreground md:inline">
                      due <RelativeTime date={item.due} />
                    </span>
                    <LeetCodeLink slug={item.slug} title={item.title} />
                    <MarkReviewedMenu slug={item.slug} title={item.title} />
                  </li>
                ))}
              </ul>
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

function AttemptedSection({ items }: { items: AttemptedItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Attempted, not yet solved ({items.length})</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col divide-y">
          {items.map((item) => (
            <li key={item.slug} className="flex items-center gap-2 py-2 text-sm">
              <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
                <ProblemTitle slug={item.slug} title={item.title} />
                <DifficultyBadge difficulty={item.difficulty} />
                {item.last_status ? (
                  <span className="text-muted-foreground">
                    last: {item.last_status}
                    {item.last_submitted_at ? (
                      <>
                        , <RelativeTime date={item.last_submitted_at} />
                      </>
                    ) : null}
                  </span>
                ) : null}
              </div>
              <LeetCodeLink slug={item.slug} title={item.title} />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
