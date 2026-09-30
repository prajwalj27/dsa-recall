import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { type Choice, endpoints, type TargetMode } from '@/lib/api'

export const keys = {
  today: ['today'] as const,
  problem: (slug: string) => ['problem', slug] as const,
  sync: ['sync'] as const,
  health: ['health'] as const,
}

/** Which environment (dev/prod) the backend runs; fixed for the server's lifetime. */
export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: endpoints.health, staleTime: Infinity })
}

export function useToday() {
  return useQuery({ queryKey: keys.today, queryFn: endpoints.today })
}

export function useProblem(slug: string | null) {
  return useQuery({
    queryKey: keys.problem(slug ?? ''),
    queryFn: () => endpoints.problem(slug!),
    enabled: slug !== null,
  })
}

/** Polls every second while a sync is running; otherwise fetched on demand. */
export function useSyncStatus() {
  return useQuery({
    queryKey: keys.sync,
    queryFn: endpoints.syncStatus,
    refetchInterval: (query) => (query.state.data?.state === 'running' ? 1000 : false),
  })
}

/** Anything that changes reviews refreshes Today and any open problem panel. */
function useInvalidateReviews() {
  const client = useQueryClient()
  return () => {
    void client.invalidateQueries({ queryKey: keys.today })
    void client.invalidateQueries({ queryKey: ['problem'] })
  }
}

export function useStartSync() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: endpoints.startSync,
    onSuccess: (status) => client.setQueryData(keys.sync, status),
  })
}

export function useRateSolve() {
  const invalidate = useInvalidateReviews()
  return useMutation({
    mutationFn: ({ solveId, choice }: { solveId: number; choice: Choice }) =>
      endpoints.rateSolve(solveId, choice),
    onSuccess: invalidate,
  })
}

export function useConfirmAll() {
  const invalidate = useInvalidateReviews()
  return useMutation({ mutationFn: endpoints.confirmAll, onSuccess: invalidate })
}

export function useMarkReviewed() {
  const invalidate = useInvalidateReviews()
  return useMutation({
    mutationFn: ({ slug, choice }: { slug: string; choice: Choice }) =>
      endpoints.markReviewed(slug, choice),
    onSuccess: invalidate,
  })
}

export function useSetTarget() {
  const invalidate = useInvalidateReviews()
  return useMutation({
    mutationFn: (body: {
      mode: TargetMode
      daily_target?: number
      retention?: number
      interview_end_date?: string | null
    }) => endpoints.putTarget(body),
    onSuccess: invalidate, // retention changes reschedule every card
  })
}

export function useSetStudyMode() {
  const invalidate = useInvalidateReviews()
  return useMutation({
    mutationFn: ({ enabled, until }: { enabled: boolean; until: string | null }) =>
      endpoints.putStudyMode(enabled, until),
    onSuccess: invalidate,
  })
}
