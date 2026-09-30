import type { Difficulty } from '@/lib/api'
import { cn } from '@/lib/utils'

const STYLE: Record<Difficulty, { short: string; className: string }> = {
  Easy: { short: 'Easy', className: 'text-easy' },
  Medium: { short: 'Med.', className: 'text-medium' },
  Hard: { short: 'Hard', className: 'text-hard' },
}

/** Difficulty as colored text (Easy / Med. / Hard); screen readers hear the full word. */
export function DifficultyText({
  difficulty,
  className,
}: {
  difficulty: Difficulty
  className?: string
}) {
  const style = STYLE[difficulty]
  return (
    <span className={cn('font-medium', style.className, className)}>
      <span aria-hidden="true">{style.short}</span>
      <span className="sr-only">{difficulty}</span>
    </span>
  )
}
