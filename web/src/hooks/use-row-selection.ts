import { useEffect, useState } from 'react'

/**
 * Row selection for bulk actions. Only rows currently shown can be selected; selection mode is
 * simply "at least one row selected". Esc clears it.
 */
export function useRowSelection(visibleSlugs: string[]) {
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const selected = visibleSlugs.filter((slug) => picked.has(slug))
  const active = selected.length > 0
  const allSelected = active && selected.length === visibleSlugs.length

  const toggle = (slug: string, on: boolean) =>
    setPicked((current) => {
      const next = new Set(current)
      if (on) next.add(slug)
      else next.delete(slug)
      return next
    })
  const setAll = (on: boolean) => setPicked(on ? new Set(visibleSlugs) : new Set())
  const clear = () => setPicked(new Set())

  useEffect(() => {
    if (!active) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPicked(new Set())
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [active])

  return {
    selected,
    active,
    allSelected,
    isSelected: (slug: string) => picked.has(slug),
    toggle,
    setAll,
    clear,
  }
}
