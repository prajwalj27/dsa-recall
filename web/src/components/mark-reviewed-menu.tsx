import { MoreHorizontal } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { CHOICES } from '@/lib/choices'
import { useMarkReviewed } from '@/lib/queries'

/** "Mark reviewed" for a re-solve done outside LeetCode (a re-solve on LeetCode syncs itself). */
export function MarkReviewedMenu({
  slug,
  title,
  trigger = 'icon',
  className,
}: {
  slug: string
  title: string
  trigger?: 'icon' | 'button'
  className?: string
}) {
  const markReviewed = useMarkReviewed()
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
