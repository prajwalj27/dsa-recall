import { toast } from 'sonner'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import type { StudyMode } from '@/lib/api'
import { useSetStudyMode } from '@/lib/queries'

/**
 * "I'm learning from solutions right now": while on, first-time solves default to
 * "Saw solution" instead of the rating inferred from wrong attempts.
 */
export function StudyModeToggle({ mode }: { mode: StudyMode }) {
  const setStudyMode = useSetStudyMode()
  const save = (enabled: boolean, until: string | null) =>
    setStudyMode.mutate({ enabled, until }, { onError: (error) => toast.error(error.message) })

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <Switch
        id="study-mode"
        checked={mode.enabled}
        onCheckedChange={(checked) => save(checked, checked ? mode.until : null)}
      />
      <Label
        htmlFor="study-mode"
        title="While on, problems you solve for the first time default to 'Saw solution'. Re-solves are still rated from your wrong attempts."
      >
        Study mode
      </Label>
      {mode.enabled ? (
        <>
          <Label htmlFor="study-until" className="text-muted-foreground">
            until
          </Label>
          <Input
            id="study-until"
            type="date"
            className="h-7 w-auto"
            value={mode.until ?? ''}
            onChange={(event) => save(true, event.target.value || null)}
          />
          {!mode.active ? <span className="text-muted-foreground">(ended)</span> : null}
        </>
      ) : null}
    </div>
  )
}
