import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { SyncStatus } from '@/lib/api'
import { useStartSync, useSyncStatus } from '@/lib/queries'
import { SYNC_ERRORS } from '@/lib/sync'

const PHASES: Record<NonNullable<SyncStatus['phase']>, string> = {
  auth: 'Checking your LeetCode session…',
  listing: 'Listing the problems you have worked on…',
  problems: 'Loading submissions and solutions…',
  scheduling: 'Scheduling your reviews…',
  done: 'Finishing up…',
}

/** Shown on Today until the first full sync (backfill) has finished. */
export function FirstRun() {
  const { data: status } = useSyncStatus()
  const startSync = useStartSync()
  const running = status?.state === 'running' || startSync.isPending
  const percent = status?.total ? Math.round((status.done / status.total) * 100) : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>Loading your LeetCode history</CardTitle>
        <CardDescription>
          The first sync reads every problem you've worked on, one request per second to stay
          polite to LeetCode. For a few hundred problems that takes about 10 minutes, and it
          resumes where it left off if interrupted.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {running && status ? (
          <>
            <p className="text-sm">{status.phase ? PHASES[status.phase] : 'Starting…'}</p>
            <Progress value={percent} aria-label="Sync progress" />
            {status.total ? (
              <p className="text-sm text-muted-foreground">
                {status.done} / {status.total} problems · {status.new_solves} solves found
              </p>
            ) : null}
          </>
        ) : (
          <>
            {status?.state === 'failed' && status.error_kind ? (
              <p className="text-sm text-destructive">
                {SYNC_ERRORS[status.error_kind]} {status.error_kind === 'other' ? status.error : ''}
              </p>
            ) : null}
            <div>
              <Button
                onClick={() =>
                  startSync.mutate(undefined, { onError: (error) => toast.error(error.message) })
                }
              >
                {status?.state === 'failed' ? 'Resume first sync' : 'Start first sync'}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
