import { Slot } from '@radix-ui/react-slot'
import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

export interface ChipProps extends ComponentProps<'button'> {
  /** Applies the selected treatment and sets `aria-pressed`. */
  selected?: boolean
  /**
   * Render as the child element. Use for chips that navigate — a link supports
   * middle-click and open-in-new-tab, which a button silently does not.
   */
  asChild?: boolean
}

/**
 * A selectable pill.
 *
 * Shared by the landing page's sample destinations and the planner's date-range
 * presets, which are the same affordance with different payloads: a bounded set
 * of one-tap shortcuts. Height clears the 44px touch target at every breakpoint.
 */
export function Chip({ className, selected = false, asChild = false, ...props }: ChipProps) {
  const Component = asChild ? Slot : 'button'

  return (
    <Component
      data-slot="chip"
      data-selected={selected || undefined}
      aria-pressed={asChild ? undefined : selected}
      className={cn(
        'inline-flex h-11 items-center justify-center rounded-full border px-4',
        'text-body whitespace-nowrap transition-colors duration-150 ease-out',
        'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
        selected
          ? 'border-primary bg-primary-subtle text-primary'
          : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
        className,
      )}
      {...props}
    />
  )
}
