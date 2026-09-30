import { Badge } from '@/components/ui/badge'
import type { Difficulty } from '@/lib/api'
import { cn } from '@/lib/utils'

const STYLES: Record<Difficulty, string> = {
  Easy: 'text-easy border-easy/40',
  Medium: 'text-medium border-medium/40',
  Hard: 'text-hard border-hard/40',
}

export function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  return (
    <Badge variant="outline" className={cn('font-medium', STYLES[difficulty])}>
      {difficulty}
    </Badge>
  )
}
