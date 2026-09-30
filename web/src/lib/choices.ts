import type { Choice } from '@/lib/api'

export const CHOICES: { value: Choice; label: string; hint: string }[] = [
  { value: 'again', label: 'Again', hint: "Couldn't solve it without help" },
  { value: 'hard', label: 'Hard', hint: 'Solved, but struggled' },
  { value: 'good', label: 'Good', hint: 'Solved with normal effort' },
  { value: 'easy', label: 'Easy', hint: 'Solved quickly and confidently' },
  {
    value: 'saw_solution',
    label: 'Saw solution',
    hint: 'Learned it from the solution; comes back soon, like Again',
  },
]

export const CHOICE_LABEL = Object.fromEntries(CHOICES.map((c) => [c.value, c.label])) as Record<
  Choice,
  string
>
