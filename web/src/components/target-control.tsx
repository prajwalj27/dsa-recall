import { Target as TargetIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { HelpPopover } from '@/components/help-popover'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Target, TargetMode } from '@/lib/api'
import { useSetTarget } from '@/lib/queries'

// Casual and Steady are fixed presets; Interview is the one adjustable mode.
const PRESETS: Partial<Record<TargetMode, { target: number; retention: number }>> = {
  casual: { target: 5, retention: 0.9 },
  steady: { target: 8, retention: 0.9 },
}
const MODES: { value: TargetMode; label: string }[] = [
  { value: 'casual', label: 'Casual' },
  { value: 'steady', label: 'Steady' },
  { value: 'interview', label: 'Interview' },
]
const MODE_LABEL = Object.fromEntries(MODES.map((m) => [m.value, m.label])) as Record<
  TargetMode,
  string
>
const RETENTIONS = [0.8, 0.85, 0.9, 0.95]

type Draft = { mode: TargetMode; number: string; retention: number }

function draftFrom(target: Target): Draft {
  return {
    mode: target.mode,
    number: String(target.interview_target),
    retention: target.interview_retention,
  }
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

/**
 * "Daily target · Steady · 8". The popover edits a draft; nothing is saved until Apply.
 * Cancel, or closing the popover, discards the draft.
 */
export function TargetControl({ target }: { target: Target }) {
  const setTarget = useSetTarget()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<Draft>(() => draftFrom(target))

  const preset = PRESETS[draft.mode]
  const number = Number(draft.number)
  const numberValid = Number.isInteger(number) && number >= 1 && number <= 100
  const changed =
    draft.mode !== target.mode ||
    (draft.mode === 'interview' &&
      (number !== target.daily_target || draft.retention !== target.retention))
  const canApply = changed && (draft.mode !== 'interview' || numberValid) && !setTarget.isPending
  const retentions = RETENTIONS.includes(draft.retention)
    ? RETENTIONS
    : [...RETENTIONS, draft.retention].sort()

  const apply = () =>
    setTarget.mutate(
      draft.mode === 'interview'
        ? { mode: 'interview', daily_target: number, retention: draft.retention }
        : { mode: draft.mode },
      {
        onSuccess: () => {
          setOpen(false)
          toast.success(`Daily target: ${MODE_LABEL[draft.mode]}`)
        },
        onError: (error) => toast.error(error.message),
      },
    )

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (next) setDraft(draftFrom(target)) // start from what's saved; closing discards
      }}
    >
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          aria-label={`Daily target: ${MODE_LABEL[target.mode]}, ${target.daily_target} reviews a day`}
        >
          <TargetIcon />
          <span className="sm:hidden">{target.daily_target}/day</span>
          <span className="hidden sm:inline">
            Daily target · {MODE_LABEL[target.mode]} · {target.daily_target}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="flex w-80 flex-col gap-4">
        <div className="flex items-center justify-between gap-2">
          <p className="font-medium">Daily target</p>
          <HelpPopover topic="the daily target">
            Your daily target is how many due reviews Today shows; the rest roll over. Retention is
            how likely you should still remember a problem when it comes due: higher means reviews
            come sooner and more are due at once. Changing it reschedules every problem. Casual and
            Steady are fixed; Interview lets you set both. This is separate from study mode, which
            only affects how new problems are rated.
          </HelpPopover>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="target-mode">Mode</Label>
          <Select
            value={draft.mode}
            onValueChange={(mode) => setDraft({ ...draft, mode: mode as TargetMode })}
          >
            <SelectTrigger id="target-mode" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MODES.map((mode) => (
                <SelectItem key={mode.value} value={mode.value}>
                  {mode.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {preset ? (
          <p className="text-sm text-muted-foreground">
            {preset.target} reviews a day · {percent(preset.retention)} retention
          </p>
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="target-number">Reviews per day</Label>
              <Input
                id="target-number"
                type="number"
                min={1}
                max={100}
                value={draft.number}
                aria-invalid={!numberValid}
                onChange={(event) => setDraft({ ...draft, number: event.target.value })}
                onKeyDown={(event) => event.key === 'Enter' && canApply && apply()}
              />
              <p className="text-xs text-muted-foreground">
                {numberValid
                  ? 'Only reviews count. New problems and suggestions never do.'
                  : 'Enter a whole number from 1 to 100.'}
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="target-retention">Retention</Label>
              <Select
                value={String(draft.retention)}
                onValueChange={(value) => setDraft({ ...draft, retention: Number(value) })}
              >
                <SelectTrigger id="target-retention" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {retentions.map((r) => (
                    <SelectItem key={r} value={String(r)}>
                      {percent(r)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Higher retention brings reviews sooner, so more come due.
              </p>
            </div>
          </>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button size="sm" disabled={!canApply} onClick={apply}>
            Apply
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
