import { Button } from '@/components/ui/button'
import type { Choice } from '@/lib/api'
import { CHOICES } from '@/lib/choices'

export function RatingButtons({
  selected,
  onSelect,
  disabled,
  size = 'sm',
}: {
  selected: Choice | null
  onSelect: (choice: Choice) => void
  disabled?: boolean
  size?: 'xs' | 'sm' // xs fits all five on one line in the narrow problem panel
}) {
  return (
    <div role="group" aria-label="Rating" className="flex flex-wrap gap-1.5">
      {CHOICES.map((choice) => {
        const isSelected = choice.value === selected
        return (
          <Button
            key={choice.value}
            size={size}
            // Selected uses the solid variant so its fill can be swapped for the rating color;
            // the outline variant's dark-mode background would override it.
            variant={isSelected ? 'default' : 'outline'}
            className={isSelected ? choice.filled : choice.outline}
            aria-pressed={isSelected}
            title={choice.hint}
            disabled={disabled}
            onClick={() => onSelect(choice.value)}
          >
            {choice.label}
          </Button>
        )
      })}
    </div>
  )
}
