import type { LucideIcon } from 'lucide-react'
import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Tone } from '@/constants/domain'
import { TONE_CLASSES } from '@/utils/domain'

export interface EmptyStateProps {
  /** 32px icon (FDS §12). */
  icon?: LucideIcon
  headline: string
  /** One explanatory line. Never more. */
  body?: ReactNode
  action?: { label: string; onClick: () => void } | undefined
  /**
   * `positive` is not a stylistic choice. "Nothing special to pack" and "No
   * significant risks" are *good outcomes* that happen to arrive as empty
   * arrays — they get the low-risk tint and reassuring tone, never a grey
   * "nothing here" treatment (FDS §12).
   */
  variant?: 'neutral' | 'positive'
  className?: string
}

const VARIANT_TONE: Record<'neutral' | 'positive', Tone> = {
  neutral: 'unknown',
  positive: 'low',
}

/** Empty state — FDS §12. Icon + headline + one line + an action. Never a bare blank region. */
export function EmptyState({
  icon: Icon = Inbox,
  headline,
  body,
  action,
  variant = 'neutral',
  className,
}: EmptyStateProps) {
  const tone = VARIANT_TONE[variant]

  return (
    <div
      className={cn(
        'flex flex-col items-center gap-3 rounded-lg px-6 py-10 text-center',
        variant === 'positive' ? TONE_CLASSES.low.surface : 'bg-muted/40',
        className,
      )}
    >
      <Icon className={cn('size-8', TONE_CLASSES[tone].text)} aria-hidden="true" />

      <p className="text-h4 font-semibold text-heading">{headline}</p>

      {body ? <p className="max-w-[46ch] text-body-sm text-muted-foreground">{body}</p> : null}

      {action ? (
        <Button variant="secondary" size="sm" onClick={action.onClick} className="mt-2">
          {action.label}
        </Button>
      ) : null}
    </div>
  )
}
