import { TriangleAlert } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { useSyncStatus } from '@/lib/queries'
import { SYNC_ERRORS } from '@/lib/sync'

/** A persistent warning when the LeetCode session has expired (toasts disappear). */
export function SyncBanner() {
  const { data: status } = useSyncStatus()
  if (status?.state !== 'failed' || status.error_kind !== 'auth_expired') return null
  return (
    <Alert variant="destructive" className="mx-4 mt-4 w-auto">
      <TriangleAlert />
      <AlertTitle>Can't sync with LeetCode</AlertTitle>
      <AlertDescription>{SYNC_ERRORS.auth_expired}</AlertDescription>
    </Alert>
  )
}
