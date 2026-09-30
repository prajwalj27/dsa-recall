import { ExternalLink, PauseCircle, PlayCircle } from 'lucide-react'
import { toast } from 'sonner'

import { DifficultyText } from '@/components/difficulty-text'
import { ProblemActionsMenu } from '@/components/problem-actions-menu'
import { RatingButtons } from '@/components/rating-buttons'
import { RelativeTime } from '@/components/relative-time'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { usePauseActions } from '@/hooks/use-pause-actions'
import { useProblemPanel } from '@/hooks/use-problem-panel'
import type { ProblemDetail, TimelineEntry } from '@/lib/api'
import { CHOICE_LABEL } from '@/lib/choices'
import { useProblem, useRateSolve } from '@/lib/queries'

/** Detail sheet for `?problem=<slug>`, available on every page. */
export function ProblemPanel() {
  const { slug, close } = useProblemPanel()
  const { data, isPending, isError, error } = useProblem(slug)

  return (
    <Sheet open={slug !== null} onOpenChange={(open) => !open && close()}>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-lg">
        {isPending ? (
          <PanelSkeleton />
        ) : isError ? (
          <SheetHeader>
            <SheetTitle>Couldn't load this problem</SheetTitle>
            <SheetDescription>{error.message}</SheetDescription>
          </SheetHeader>
        ) : (
          <PanelBody detail={data} />
        )}
      </SheetContent>
    </Sheet>
  )
}

function PanelSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-4">
      <SheetTitle className="sr-only">Loading problem</SheetTitle>
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-24 w-full" />
    </div>
  )
}

function PanelBody({ detail }: { detail: ProblemDetail }) {
  const { problem, card, timeline } = detail
  return (
    <>
      <SheetHeader className="gap-2 border-b">
        <SheetTitle className="pr-8 text-lg">
          {problem.frontend_id ? `${problem.frontend_id}. ` : ''}
          {problem.title}
        </SheetTitle>
        <SheetDescription asChild>
          <div className="flex flex-wrap items-center gap-2">
            <DifficultyText difficulty={problem.difficulty} />
            {problem.is_paid_only ? <Badge variant="secondary">Premium</Badge> : null}
            {problem.ac_rate !== null ? (
              <span>{problem.ac_rate.toFixed(1)}% acceptance</span>
            ) : null}
          </div>
        </SheetDescription>
        {problem.topic_tags.length ? (
          <div className="flex flex-wrap gap-1">
            {problem.topic_tags.map((tag) => (
              <Badge key={tag.slug} variant="secondary" className="font-normal">
                {tag.name}
              </Badge>
            ))}
          </div>
        ) : null}
        <div>
          <Button asChild size="sm" variant="outline">
            <a href={problem.url} target="_blank" rel="noreferrer">
              <ExternalLink />
              Open on LeetCode
            </a>
          </Button>
        </div>
      </SheetHeader>

      <section className="flex flex-col gap-3 border-b p-4" aria-labelledby="review-heading">
        <div className="flex items-center justify-between gap-2">
          <h3 id="review-heading" className="font-medium">
            Review
          </h3>
          <div className="flex flex-wrap justify-end gap-2">
            <PauseToggle slug={problem.slug} title={problem.title} paused={problem.paused} />
            {card ? (
              <ProblemActionsMenu slug={problem.slug} title={problem.title} trigger="button" />
            ) : null}
          </div>
        </div>
        {problem.paused ? (
          <p className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
            {card
              ? 'Paused: not in your review queue. Solving it again resumes it.'
              : 'Paused: hidden from "Attempted, not yet solved". Solving it resumes it.'}
          </p>
        ) : null}
        {card ? (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Next review</dt>
            <dd>
              <RelativeTime date={card.due} />
            </dd>
            <dt className="text-muted-foreground">Recall now</dt>
            <dd>{Math.round(card.recall * 100)}%</dd>
            <dt className="text-muted-foreground">Reviews</dt>
            <dd>
              {card.reps}
              {card.lapses ? ` · ${card.lapses} forgotten` : ''}
            </dd>
          </dl>
        ) : (
          <p className="text-sm text-muted-foreground">
            Not solved yet, so no reviews are scheduled.
          </p>
        )}
      </section>

      <section className="flex flex-col gap-3 p-4" aria-labelledby="history-heading">
        <h3 id="history-heading" className="font-medium">
          History
        </h3>
        <ol className="flex flex-col gap-4">
          {timeline.map((entry) => (
            <TimelineItem key={`${entry.kind}-${entry.at}`} entry={entry} />
          ))}
        </ol>
      </section>
    </>
  )
}

function PauseToggle({ slug, title, paused }: { slug: string; title: string; paused: boolean }) {
  const { pauseProblems, resumeProblems, pending } = usePauseActions()
  return paused ? (
    <Button size="sm" disabled={pending} onClick={() => resumeProblems({ slugs: [slug] }, title)}>
      <PlayCircle />
      Resume reviews
    </Button>
  ) : (
    <Button
      variant="outline"
      size="sm"
      disabled={pending}
      onClick={() => pauseProblems([slug], title)}
    >
      <PauseCircle />
      Pause reviews
    </Button>
  )
}

const SOURCE_NOTE = {
  history: 'Inferred from your history',
  inferred: 'Waiting for your rating',
  user: 'Your rating',
} as const

function TimelineItem({ entry }: { entry: TimelineEntry }) {
  const rateSolve = useRateSolve()

  return (
    <li className="flex flex-col gap-2 border-l-2 pl-3">
      <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
        <span className="font-medium">
          {entry.kind === 'solve'
            ? 'Solved'
            : entry.kind === 'review'
              ? `Marked reviewed · ${entry.choice ? CHOICE_LABEL[entry.choice] : ''}`
              : 'Attempted since last solve'}
        </span>
        <RelativeTime date={entry.at} className="text-muted-foreground" />
        {entry.kind === 'solve' && entry.wrong_before_ac !== null ? (
          <span className="text-muted-foreground">
            · {entry.wrong_before_ac} wrong attempt{entry.wrong_before_ac === 1 ? '' : 's'}
          </span>
        ) : null}
      </div>

      {entry.kind === 'solve' && entry.solve_id !== null ? (
        <div className="flex flex-col gap-1">
          <RatingButtons
            size="xs"
            selected={entry.choice}
            disabled={rateSolve.isPending}
            onSelect={(choice) =>
              rateSolve.mutate(
                { solveId: entry.solve_id!, choice },
                { onError: (error) => toast.error(error.message) },
              )
            }
          />
          {entry.rating_source ? (
            <span className="text-xs text-muted-foreground">{SOURCE_NOTE[entry.rating_source]}</span>
          ) : null}
        </div>
      ) : null}

      {entry.submissions.length ? (
        <ul className="flex flex-col gap-0.5 text-xs text-muted-foreground">
          {entry.submissions.map((sub) => (
            <li key={sub.id} className="flex flex-wrap gap-x-2">
              <span className={sub.status === 'Accepted' ? 'text-easy' : 'text-hard'}>
                {sub.status}
              </span>
              <span>{sub.lang}</span>
              {sub.runtime_ms !== null ? <span>{sub.runtime_ms} ms</span> : null}
              <RelativeTime date={sub.at} />
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  )
}
