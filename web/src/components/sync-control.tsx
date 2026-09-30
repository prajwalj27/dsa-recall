import { useQueryClient } from '@tanstack/react-query'
import { Loader2, RefreshCw } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { toast } from 'sonner'

import { RelativeTime } from '@/components/relative-time'
import { Button } from '@/components/ui/button'
import type { SyncStatus } from '@/lib/api'
import { invalidateReviewData, useStartSync, useSyncStatus } from '@/lib/queries'
import { SYNC_ERRORS, syncProgressLabel } from '@/lib/sync'

// Module-level so React StrictMode's double-mounted effects can't sync twice.
let autoSyncStarted = false

/** Top bar: last synced time, the Sync button, and live progress while syncing. */
export function SyncControl() {
  const client = useQueryClient()
  const { data: status } = useSyncStatus()
  const startSync = useStartSync()
  const previousState = useRef<SyncStatus['state'] | undefined>(undefined)
  const manual = useRef(false)

  // Built app only: sync once when it opens. `npm run dev` never syncs on its own,
  // so hot reloads don't hit LeetCode.
  useEffect(() => {
    if (import.meta.env.PROD && !autoSyncStarted) {
      autoSyncStarted = true
      startSync.mutate()
    }
  }, [startSync])

  // When a run finishes: refresh data and report the outcome.
  useEffect(() => {
    const state = status?.state
    if (previousState.current === 'running' && state && state !== 'running') {
      invalidateReviewData(client)
      if (state === 'failed' && status.error_kind) {
        const detail = status.error_kind === 'other' ? ` ${status.error ?? ''}` : ''
        toast.error(SYNC_ERRORS[status.error_kind] + detail)
      } else if (state === 'succeeded' && (manual.current || status.new_solves > 0)) {
        toast.success(
          status.new_solves > 0
            ? `Synced: ${status.new_solves} new solve${status.new_solves === 1 ? '' : 's'}`
            : 'Up to date',
        )
      }
      manual.current = false
    }
    previousState.current = state
  }, [status, client])

  const running = status?.state === 'running' || startSync.isPending

  return (
    <div className="flex items-center gap-3 text-sm text-muted-foreground">
      <span className="hidden sm:inline" aria-live="polite">
        {running && status ? (
          syncProgressLabel(status)
        ) : status?.last_sync_at ? (
          <>
            Last synced <RelativeTime date={status.last_sync_at} />
          </>
        ) : (
          'Never synced'
        )}
      </span>
      <Button
        size="sm"
        variant="outline"
        disabled={running}
        onClick={() => {
          manual.current = true
          startSync.mutate(undefined, { onError: (error) => toast.error(error.message) })
        }}
      >
        {running ? <Loader2 className="animate-spin" /> : <RefreshCw />}
        Sync
      </Button>
    </div>
  )
}
