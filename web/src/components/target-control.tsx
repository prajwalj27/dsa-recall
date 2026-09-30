import { Target as TargetIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

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

const MODES: { value: TargetMode; label: string; description: string }[] = [
  { value: 'casual', label: 'Casual', description: 'About 5 reviews a day, 90% retention' },
  { value: 'steady', label: 'Steady', description: 'About 8 reviews a day, 90% retention' },
  {
    value: 'interview',
    label: 'Interview prep',
    description: 'About 15 reviews a day, 95% retention; reviews come sooner',
  },
  { value: 'custom', label: 'Custom', description: 'Your own number and retention' },
]
const MODE_LABEL = Object.fromEntries(MODES.map((m) => [m.value, m.label])) as Record<
  TargetMode,
  string
>
const RETENTIONS = [0.8, 0.85, 0.9, 0.95]

/** "Daily target · Steady · 8" with a popover to change mode, number, retention, end date. */
export function TargetControl({ target }: { target: Target }) {
  const setTarget = useSetTarget()
  const [draft, setDraft] = useState(String(target.daily_target))
  const [open, setOpen] = useState(false)

  const save = (body: Parameters<typeof setTarget.mutate>[0]) =>
    setTarget.mutate(body, { onError: (error) => toast.error(error.message) })

  const commitNumber = () => {
    const value = Number(draft)
    if (Number.isInteger(value) && value >= 1 && value <= 100) {
      if (value !== target.daily_target) save({ mode: target.mode, daily_target: value })
    } else {
      setDraft(String(target.daily_target))
    }
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (next) setDraft(String(target.daily_target))
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm">
          <TargetIcon />
          Daily target · {MODE_LABEL[target.mode]} · {target.daily_target}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="flex w-80 flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="target-mode">Mode</Label>
          <Select
            value={target.mode}
            onValueChange={(mode) =>
              save({
                mode: mode as TargetMode,
                ...(mode === 'interview' ? { interview_end_date: target.interview_end_date } : {}),
              })
            }
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
          <p className="text-xs text-muted-foreground">
            {MODES.find((m) => m.value === target.mode)?.description}
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="target-number">Reviews per day</Label>
          <Input
            id="target-number"
            type="number"
            min={1}
            max={100}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commitNumber}
            onKeyDown={(event) => event.key === 'Enter' && commitNumber()}
          />
          <p className="text-xs text-muted-foreground">
            Only reviews count. New problems and suggestions never do.
          </p>
        </div>

        {target.mode === 'custom' ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="target-retention">Desired retention</Label>
            <Select
              value={String(target.retention)}
              onValueChange={(value) => save({ mode: 'custom', retention: Number(value) })}
            >
              <SelectTrigger id="target-retention" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RETENTIONS.map((r) => (
                  <SelectItem key={r} value={String(r)}>
                    {Math.round(r * 100)}%
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Higher retention schedules reviews sooner, so more come due.
            </p>
          </div>
        ) : null}

        {target.mode === 'interview' ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="interview-end">Interview prep ends</Label>
            <Input
              id="interview-end"
              type="date"
              value={target.interview_end_date ?? ''}
              onChange={(event) =>
                save({ mode: 'interview', interview_end_date: event.target.value || null })
              }
            />
            <p className="text-xs text-muted-foreground">
              Optional. Afterwards, your previous mode
              {target.previous_mode ? ` (${MODE_LABEL[target.previous_mode]})` : ''} comes back.
            </p>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}
