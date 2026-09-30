import { toast } from 'sonner'

import { usePause, useResume } from '@/lib/queries'

/** Pause / resume with toasts; pausing offers Undo, which resumes exactly those problems. */
export function usePauseActions() {
  const pause = usePause()
  const resume = useResume()

  const pauseProblems = (slugs: string[], label: string, onDone?: () => void) =>
    pause.mutate(slugs, {
      onSuccess: () => {
        onDone?.()
        toast.success(`Paused ${label}`, {
          description: 'Out of your reviews until you resume it or solve it again.',
          action: {
            label: 'Undo',
            onClick: () =>
              resume.mutate({ slugs }, { onError: (error) => toast.error(error.message) }),
          },
        })
      },
      onError: (error) => toast.error(error.message),
    })

  const resumeProblems = (target: { slugs: string[] } | { all: true }, label: string) =>
    resume.mutate(target, {
      onSuccess: () => toast.success(`Resumed ${label}`),
      onError: (error) => toast.error(error.message),
    })

  return { pauseProblems, resumeProblems, pending: pause.isPending || resume.isPending }
}

export function problemCount(n: number): string {
  return `${n} problem${n === 1 ? '' : 's'}`
}
