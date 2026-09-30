import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { TableCell, TableHead } from '@/components/ui/table'
import { cn } from '@/lib/utils'

// The column is always there (so rows don't shift). Until a selection starts, a row's checkbox
// is invisible and appears on row hover or keyboard focus; touch devices always show it.
const REVEAL =
  'opacity-0 group-hover:opacity-100 focus-visible:opacity-100 [@media(hover:none)]:opacity-100'

export function SelectHead({
  active,
  allSelected,
  onSetAll,
  className,
}: {
  active: boolean
  allSelected: boolean
  onSetAll: (on: boolean) => void
  className?: string
}) {
  return (
    <TableHead className={cn('w-8', className)}>
      {active ? (
        <Checkbox
          aria-label="Select all shown"
          checked={allSelected ? true : 'indeterminate'}
          onCheckedChange={(on) => onSetAll(on === true)}
        />
      ) : (
        <span className="sr-only">Select</span>
      )}
    </TableHead>
  )
}

export function SelectCell({
  label,
  checked,
  active,
  onChange,
}: {
  label: string
  checked: boolean
  active: boolean
  onChange: (on: boolean) => void
}) {
  return (
    <TableCell className="w-8">
      <Checkbox
        aria-label={label}
        checked={checked}
        className={cn(!active && REVEAL)}
        onCheckedChange={(on) => onChange(on === true)}
      />
    </TableCell>
  )
}

/** "N selected · [action] · Clear", shown while rows are selected. */
export function SelectionBar({
  count,
  onClear,
  children,
}: {
  count: number
  onClear: () => void
  children: ReactNode
}) {
  return (
    <div
      className="sticky top-2 z-10 flex flex-wrap items-center gap-2 rounded-md border bg-card px-3 py-2 text-sm shadow-sm"
      role="toolbar"
      aria-label="Selection"
    >
      <span className="text-muted-foreground">{count} selected</span>
      <div className="ml-auto flex items-center gap-2">
        {children}
        <Button variant="ghost" size="sm" onClick={onClear}>
          Clear
        </Button>
      </div>
    </div>
  )
}
