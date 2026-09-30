import { MoreHorizontal, PauseCircle } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { usePauseActions } from '@/hooks/use-pause-actions'
import { CHOICES } from '@/lib/choices'
import { useMarkReviewed } from '@/lib/queries'

/**
 * Row actions for a problem with a card: pause its reviews, or mark it reviewed (a re-solve
 * done outside LeetCode; a re-solve on LeetCode syncs itself).
 */
export function ProblemActionsMenu({
  slug,
  title,
  trigger = 'icon',
  showPause = true,
  className,
}: {
  slug: string
  title: string
  trigger?: 'icon' | 'button'
  showPause?: boolean
  className?: string
}) {
  const markReviewed = useMarkReviewed()
  const { pauseProblems } = usePauseActions()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {trigger === 'icon' ? (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${title}`}
            className={className}
          >
            <MoreHorizontal />
          </Button>
        ) : (
          <Button variant="outline" size="sm">
            Mark reviewed
          </Button>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {showPause ? (
          <>
            <DropdownMenuItem onSelect={() => pauseProblems([slug], title)}>
              <PauseCircle />
              Pause reviews
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        ) : null}
        <DropdownMenuLabel>Mark reviewed as</DropdownMenuLabel>
        {CHOICES.map((choice) => (
          <DropdownMenuItem
            key={choice.value}
            onSelect={() =>
              markReviewed.mutate(
                { slug, choice: choice.value },
                {
                  onSuccess: () => toast.success(`Reviewed ${title}`),
                  onError: (error) => toast.error(error.message),
                },
              )
            }
          >
            {choice.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
