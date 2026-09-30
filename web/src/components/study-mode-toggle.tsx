import { toast } from 'sonner'

import { HelpPopover } from '@/components/help-popover'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import type { StudyMode } from '@/lib/api'
import { useSetStudyMode } from '@/lib/queries'

/**
 * "I'm learning from solutions right now": while on, first-time solves default to
 * "Saw solution" instead of the rating inferred from wrong attempts. On until switched off.
 */
export function StudyModeToggle({ mode }: { mode: StudyMode }) {
  const setStudyMode = useSetStudyMode()

  return (
    <div className="flex flex-col items-end gap-1 text-sm @max-md/card-header:items-start">
      <div className="flex items-center gap-2">
        <Switch
          id="study-mode"
          checked={mode.enabled}
          disabled={setStudyMode.isPending}
          onCheckedChange={(checked) =>
            setStudyMode.mutate(checked, { onError: (error) => toast.error(error.message) })
          }
        />
        <Label htmlFor="study-mode">Study mode</Label>
        <HelpPopover topic="study mode">
          Use this while learning from solutions. Problems you solve for the first time default to
          "Saw solution", so they come back in about a day instead of being treated as solved on
          your own. Re-solves are still rated from your wrong attempts. It stays on until you switch
          it off, and doesn't change your daily target or retention.
        </HelpPopover>
      </div>
      {mode.enabled ? (
        <p className="text-right text-xs text-muted-foreground @max-md/card-header:text-left">
          New problems default to "Saw solution". Re-solves are rated normally.
        </p>
      ) : null}
    </div>
  )
}
