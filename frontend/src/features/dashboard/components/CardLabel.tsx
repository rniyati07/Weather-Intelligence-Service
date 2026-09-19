import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

/**
 * The small icon + caption that titles each verdict-band card.
 *
 * Extracted only because four sibling cards render it identically and a drift
 * of two pixels between them would be visible in a row — not because it is
 * reusable beyond this band.
 */
export function CardLabel({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-caption font-medium text-muted-foreground">
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      {children}
    </p>
  )
}
