import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useNow } from '@/hooks/use-now'
import { exactTime, relativeTime } from '@/lib/time'

/** "3 days ago" / "in 2 months", with the exact local date and time on hover. */
export function RelativeTime({ date, className }: { date: string; className?: string }) {
  const now = useNow()
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <time dateTime={date} className={className}>
          {relativeTime(date, now)}
        </time>
      </TooltipTrigger>
      <TooltipContent>{exactTime(date)}</TooltipContent>
    </Tooltip>
  )
}
