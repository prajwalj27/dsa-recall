import { Button } from '@/components/ui/button'
import type { Choice } from '@/lib/api'
import { CHOICES } from '@/lib/choices'

export function RatingButtons({
  selected,
  onSelect,
  disabled,
}: {
  selected: Choice | null
  onSelect: (choice: Choice) => void
  disabled?: boolean
}) {
  return (
    <div role="group" aria-label="Rating" className="flex flex-wrap gap-1.5">
      {CHOICES.map((choice) => (
        <Button
          key={choice.value}
          size="sm"
          variant={choice.value === selected ? 'default' : 'outline'}
          aria-pressed={choice.value === selected}
          title={choice.hint}
          disabled={disabled}
          onClick={() => onSelect(choice.value)}
        >
          {choice.label}
        </Button>
      ))}
    </div>
  )
}
