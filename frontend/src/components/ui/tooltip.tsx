import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import type { ComponentProps, ReactNode } from 'react'

import { TOOLTIP_DELAY_MS } from '@/constants/motion'
import { cn } from '@/lib/utils'

/**
 * Tooltip — FDS §11.2.
 *
 * Radix underneath, so keyboard focus opens it and Escape closes it: a tooltip
 * that only responds to hover is invisible to keyboard and touch users, and
 * **all hover affordances must have a non-hover equivalent**.
 *
 * Corollary for call sites: a tooltip may only ever *supplement* information
 * that is already on screen. It is where the exact activity score or the `rule`
 * id lives — never where a verdict lives.
 */
export function TooltipProvider({
  delayDuration = TOOLTIP_DELAY_MS,
  ...props
}: ComponentProps<typeof TooltipPrimitive.Provider>) {
  return <TooltipPrimitive.Provider delayDuration={delayDuration} {...props} />
}

export function TooltipRoot(props: ComponentProps<typeof TooltipPrimitive.Root>) {
  return <TooltipPrimitive.Root {...props} />
}

export function TooltipTrigger(props: ComponentProps<typeof TooltipPrimitive.Trigger>) {
  return <TooltipPrimitive.Trigger {...props} />
}

export function TooltipContent({
  className,
  sideOffset = 6,
  children,
  ...props
}: ComponentProps<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          'border-border bg-surface-raised text-foreground shadow-md',
          'z-50 max-w-64 rounded-md border px-3 py-2 text-body-sm',
          'data-[state=closed]:animate-out data-[state=delayed-open]:animate-in',
          'data-[state=closed]:fade-out-0 data-[state=delayed-open]:fade-in-0',
          className,
        )}
        {...props}
      >
        {children}
        <TooltipPrimitive.Arrow className="fill-surface-raised" />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  )
}

/**
 * The common case in one component: wrap a trigger, pass the text.
 * Compose the primitives directly when the trigger needs controlled state.
 */
export function Tooltip({
  content,
  children,
  side = 'top',
  ...props
}: {
  content: ReactNode
  children: ReactNode
  side?: ComponentProps<typeof TooltipPrimitive.Content>['side']
} & Omit<ComponentProps<typeof TooltipPrimitive.Root>, 'children'>) {
  return (
    <TooltipRoot {...props}>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side={side}>{content}</TooltipContent>
    </TooltipRoot>
  )
}
