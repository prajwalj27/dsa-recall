import { cn } from '@/lib/utils'

/** Red below 50%, amber below 75%, green above; the number is always shown too. */
function tone(recall: number): string {
  if (recall < 0.5) return 'bg-hard'
  if (recall < 0.75) return 'bg-medium'
  return 'bg-easy'
}

/** Current recall as a short bar plus a percentage. */
export function RecallMeter({ recall }: { recall: number }) {
  const percent = Math.round(recall * 100)
  return (
    <div
      role="meter"
      aria-label="Recall"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      className="flex items-center justify-end gap-2"
    >
      <div className="h-1.5 w-12 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <div className={cn('h-full rounded-full', tone(recall))} style={{ width: `${percent}%` }} />
      </div>
      <span className="w-9 text-right tabular-nums">{percent}%</span>
    </div>
  )
}
