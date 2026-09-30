import { ExternalLink } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useProblemPanel } from '@/hooks/use-problem-panel'
import { cn } from '@/lib/utils'

/** "410. Split Array Largest Sum": opens the detail panel. Truncates, full title on hover. */
export function ProblemTitle({
  slug,
  title,
  frontendId,
  className,
}: {
  slug: string
  title: string
  frontendId?: string | null
  className?: string
}) {
  const { open } = useProblemPanel()
  const label = frontendId ? `${frontendId}. ${title}` : title
  return (
    <button
      type="button"
      onClick={() => open(slug)}
      title={label}
      className={cn(
        'block max-w-full truncate text-left font-medium hover:underline focus-visible:underline focus-visible:outline-none',
        className,
      )}
    >
      {label}
    </button>
  )
}

function leetcodeUrl(slug: string): string {
  return `https://leetcode.com/problems/${slug}/`
}

/** Icon button that opens the problem on leetcode.com in a new tab. */
export function LeetCodeLink({
  slug,
  title,
  className,
}: {
  slug: string
  title: string
  className?: string
}) {
  return (
    <Button asChild variant="ghost" size="icon-sm" className={cn(className)}>
      <a
        href={leetcodeUrl(slug)}
        target="_blank"
        rel="noreferrer"
        aria-label={`Open ${title} on LeetCode`}
        title="Open on LeetCode"
      >
        <ExternalLink />
      </a>
    </Button>
  )
}
