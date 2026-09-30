import type { SyncStatus } from '@/lib/api'

export const SYNC_ERRORS: Record<NonNullable<SyncStatus['error_kind']>, string> = {
  auth_expired:
    'LeetCode session expired. Copy a fresh LEETCODE_SESSION and csrftoken from your browser into .env, then restart DSA Recall.',
  rate_limited: 'LeetCode is rate limiting requests. Try syncing again in a few minutes.',
  schema_changed: 'LeetCode changed its API, so sync is broken until DSA Recall is updated.',
  other: 'Sync failed.',
}

export function syncProgressLabel(status: SyncStatus): string {
  if (status.phase === 'problems' && status.total) return `Syncing ${status.done} / ${status.total}`
  if (status.phase === 'scheduling') return 'Scheduling reviews…'
  return 'Syncing…'
}
