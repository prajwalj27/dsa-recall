import { useQuery } from '@tanstack/react-query'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type Health } from '@/lib/api'

const SECTIONS = ['Rate your new solves', 'Due for review', 'Attempted, not yet solved', 'Suggested']

export function TodayPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<Health>('/health') })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <h1 className="text-2xl font-semibold">Today</h1>
      <p className="text-sm text-muted-foreground">
        Backend:{' '}
        {health.isPending
          ? 'checking…'
          : health.isError
            ? 'unreachable'
            : `${health.data.status} (v${health.data.version})`}
      </p>
      {SECTIONS.map((title) => (
        <Card key={title}>
          <CardHeader>
            <CardTitle>{title}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">Nothing here yet.</CardContent>
        </Card>
      ))}
    </div>
  )
}
