import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

/** The problem detail panel is driven by `?problem=<slug>`, so it works from any page. */
export function useProblemPanel() {
  const [params, setParams] = useSearchParams()
  const slug = params.get('problem')

  const open = useCallback(
    (next: string) =>
      setParams((current) => {
        const updated = new URLSearchParams(current)
        updated.set('problem', next)
        return updated
      }),
    [setParams],
  )

  const close = useCallback(
    () =>
      setParams((current) => {
        const updated = new URLSearchParams(current)
        updated.delete('problem')
        return updated
      }),
    [setParams],
  )

  return { slug, open, close }
}
