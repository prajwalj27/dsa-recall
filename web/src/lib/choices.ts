import type { Choice } from '@/lib/api'

type ChoiceInfo = {
  value: Choice
  label: string
  hint: string
  // Static class strings (Tailwind can't see dynamically built names).
  outline: string // unselected button
  filled: string // selected button
  dot: string // menu marker
}

/** Rating choices ordered worst -> best, each with its own color (a second cue to the label). */
export const CHOICES: ChoiceInfo[] = [
  {
    value: 'saw_solution',
    label: 'Saw solution',
    hint: 'Learned it from the solution; comes back soon, like Again',
    outline: 'text-rate-saw border-rate-saw/40 hover:bg-rate-saw/10 hover:text-rate-saw dark:border-rate-saw/40 dark:hover:bg-rate-saw/10',
    filled: 'bg-rate-saw text-background border-transparent hover:bg-rate-saw/90',
    dot: 'bg-rate-saw',
  },
  {
    value: 'again',
    label: 'Again',
    hint: "Couldn't solve it without help",
    outline: 'text-rate-again border-rate-again/40 hover:bg-rate-again/10 hover:text-rate-again dark:border-rate-again/40 dark:hover:bg-rate-again/10',
    filled: 'bg-rate-again text-background border-transparent hover:bg-rate-again/90',
    dot: 'bg-rate-again',
  },
  {
    value: 'hard',
    label: 'Hard',
    hint: 'Solved, but struggled',
    outline: 'text-rate-hard border-rate-hard/40 hover:bg-rate-hard/10 hover:text-rate-hard dark:border-rate-hard/40 dark:hover:bg-rate-hard/10',
    filled: 'bg-rate-hard text-background border-transparent hover:bg-rate-hard/90',
    dot: 'bg-rate-hard',
  },
  {
    value: 'good',
    label: 'Good',
    hint: 'Solved with normal effort',
    outline: 'text-rate-good border-rate-good/40 hover:bg-rate-good/10 hover:text-rate-good dark:border-rate-good/40 dark:hover:bg-rate-good/10',
    filled: 'bg-rate-good text-background border-transparent hover:bg-rate-good/90',
    dot: 'bg-rate-good',
  },
  {
    value: 'easy',
    label: 'Easy',
    hint: 'Solved quickly and confidently',
    outline: 'text-rate-easy border-rate-easy/40 hover:bg-rate-easy/10 hover:text-rate-easy dark:border-rate-easy/40 dark:hover:bg-rate-easy/10',
    filled: 'bg-rate-easy text-background border-transparent hover:bg-rate-easy/90',
    dot: 'bg-rate-easy',
  },
]

export const CHOICE_LABEL = Object.fromEntries(CHOICES.map((c) => [c.value, c.label])) as Record<
  Choice,
  string
>
