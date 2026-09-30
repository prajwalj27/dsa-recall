import { ExternalLink } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useProblemPanel } from '@/hooks/use-problem-panel'

/** A problem title that opens the detail panel. */
export function ProblemTitle({ slug, title }: { slug: string; title: string }) {
  const { open } = useProblemPanel()
  return (
    <button
      type="button"
      onClick={() => open(slug)}
      className="truncate text-left font-medium hover:underline focus-visible:underline focus-visible:outline-none"
    >
      {title}
    </button>
  )
}

function leetcodeUrl(slug: string): string {
  return `https://leetcode.com/problems/${slug}/`
}

/** Icon button that opens the problem on leetcode.com in a new tab. */
export function LeetCodeLink({ slug, title }: { slug: string; title: string }) {
  return (
    <Button asChild variant="ghost" size="icon-sm">
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
