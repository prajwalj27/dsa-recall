import { HelpCircle } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

/**
 * A small (?) button that opens an explanation. Unlike a hover `title`, it works with the
 * keyboard (Enter/Space opens, Esc closes) and on touch screens.
 */
export function HelpPopover({ topic, children }: { topic: string; children: ReactNode }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`About ${topic}`}
          className="text-muted-foreground hover:text-foreground"
        >
          <HelpCircle />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 text-sm leading-relaxed">
        {children}
      </PopoverContent>
    </Popover>
  )
}
