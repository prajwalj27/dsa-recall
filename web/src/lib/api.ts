/**
 * Typed client for the FastAPI backend (proxied to /api in dev).
 * Types mirror app/api/schemas.py; timestamps are ISO 8601 UTC strings.
 */

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    let message = `${init?.method ?? 'GET'} /api${path} failed: ${response.status}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // not JSON; keep the generic message
    }
    throw new ApiError(response.status, message)
  }
  return response.json() as Promise<T>
}

const send = <T>(method: string, path: string, body: unknown) =>
  api<T>(path, { method, body: JSON.stringify(body) })

export type Health = { status: string; version: string; env: 'dev' | 'prod'; database: string }

// --- Shared ------------------------------------------------------------------------------

export type Difficulty = 'Easy' | 'Medium' | 'Hard'
export type Choice = 'again' | 'hard' | 'good' | 'easy' | 'saw_solution'
export type TargetMode = 'casual' | 'steady' | 'interview' | 'custom'

// --- Today --------------------------------------------------------------------------------

export type PendingItem = {
  solve_id: number
  slug: string
  title: string
  difficulty: Difficulty
  accepted_at: string
  wrong_before_ac: number
  default: Choice | null
  frontend_id: string | null
}

export type DueItem = {
  slug: string
  title: string
  difficulty: Difficulty
  due: string
  recall: number
  priority: number
  frontend_id: string | null
  last_review: string | null
}

export type DueSection = {
  items: DueItem[]
  shown: number
  total_due: number
  done_today: number
  target: number
}

export type AttemptedItem = {
  slug: string
  title: string
  difficulty: Difficulty
  frontend_id: string | null
  last_status: string | null
  last_submitted_at: string | null
}

export type StudyMode = { enabled: boolean; until: string | null; active: boolean }

export type Target = {
  mode: TargetMode
  daily_target: number
  retention: number
  interview_end_date: string | null
  previous_mode: TargetMode | null
}

export type Today = {
  pending: PendingItem[]
  due: DueSection
  attempted: AttemptedItem[]
  study_mode: StudyMode
  target: Target
  backfill_done: boolean
}

// --- Problem detail ------------------------------------------------------------------------

export type ProblemDetail = {
  problem: {
    slug: string
    title: string
    difficulty: Difficulty
    frontend_id: string | null
    topic_tags: { name: string; slug: string }[]
    ac_rate: number | null
    is_paid_only: boolean
    url: string
  }
  card: {
    due: string
    recall: number
    reps: number
    lapses: number
    suspended: boolean
    last_review: string | null
  } | null
  timeline: TimelineEntry[]
}

export type TimelineEntry = {
  kind: 'solve' | 'review' | 'attempts'
  at: string
  solve_id: number | null
  wrong_before_ac: number | null
  choice: Choice | null
  rating_source: 'history' | 'inferred' | 'user' | null
  submissions: {
    id: number
    status: string
    lang: string
    runtime_ms: number | null
    at: string
  }[]
}

// --- Sync ------------------------------------------------------------------------------------

export type SyncStatus = {
  state: 'idle' | 'running' | 'succeeded' | 'failed'
  mode: 'backfill' | 'incremental' | null
  phase: 'auth' | 'listing' | 'problems' | 'scheduling' | 'done' | null
  done: number
  total: number | null
  current_slug: string | null
  new_submissions: number
  new_solves: number
  scheduled: number
  started_at: string | null
  finished_at: string | null
  error_kind: 'auth_expired' | 'rate_limited' | 'schema_changed' | 'other' | null
  error: string | null
  last_sync_at: string | null
  backfill_done: boolean
}

// --- Endpoints ---------------------------------------------------------------------------

export const endpoints = {
  health: () => api<Health>('/health'),
  today: () => api<Today>('/today'),
  problem: (slug: string) => api<ProblemDetail>(`/problems/${encodeURIComponent(slug)}`),
  markReviewed: (slug: string, choice: Choice) =>
    send('POST', `/problems/${encodeURIComponent(slug)}/review`, { choice }),
  rateSolve: (solveId: number, choice: Choice) =>
    send('POST', `/solves/${solveId}/rating`, { choice }),
  confirmAll: (solveIds: number[]) =>
    send<{ confirmed: number }>('POST', '/solves/confirm', { solve_ids: solveIds }),
  putTarget: (body: {
    mode: TargetMode
    daily_target?: number
    retention?: number
    interview_end_date?: string | null
  }) => send<Target>('PUT', '/settings/target', body),
  putStudyMode: (enabled: boolean, until: string | null) =>
    send<StudyMode>('PUT', '/settings/study-mode', { enabled, until }),
  syncStatus: () => api<SyncStatus>('/sync/status'),
  startSync: () => send<SyncStatus>('POST', '/sync', {}),
}
