import { Copy, Check, TriangleAlert } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useCopyToClipboard } from '@/hooks/useCopyToClipboard'
import { cn } from '@/lib/utils'

export interface ErrorStateProps {
  headline: string
  /** Plain language. Never the raw `error.message` from the API (FDS §13.1). */
  body: string
  /** Primary recovery action. Omit only when there is genuinely nothing to offer. */
  action?: { label: string; onClick: () => void; loading?: boolean } | undefined
  /** Shown click-to-copy on every 4xx/5xx, for support. */
  requestId?: string | undefined
  icon?: LucideIcon
  /**
   * `page` fills the viewport region; `inline` is a compact block for a card or
   * a section. A narration failure uses `inline` with `severity="muted"` — it
   * is a degradation, not a failure, and must feel like one (FDS §13.4).
   */
  layout?: 'page' | 'inline'
  /** `muted` for degradations; `error` for genuine failures. Never red for stale data. */
  severity?: 'error' | 'muted'
  className?: string
}

/**
 * Error state — FDS §13.
 *
 * Four rules it exists to enforce: plain language, always say what to do next,
 * `requestId` reachable, and scope the error to the smallest region that
 * actually failed. It never surfaces provider names, stack traces or internal
 * detail — the backend guarantees it won't send them, and this is the last
 * place that could leak them.
 */
export function ErrorState({
  headline,
  body,
  action,
  requestId,
  icon: Icon = TriangleAlert,
  layout = 'page',
  severity = 'error',
  className,
}: ErrorStateProps) {
  const { copied, copy } = useCopyToClipboard()

  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col rounded-lg',
        layout === 'page'
          ? 'items-center gap-4 px-6 py-16 text-center'
          : 'items-start gap-3 px-5 py-6 text-left',
        severity === 'error' ? 'bg-risk-high-surface' : 'bg-muted/60',
        className,
      )}
    >
      <Icon
        className={cn(
          layout === 'page' ? 'size-12' : 'size-6',
          severity === 'error' ? 'text-risk-high' : 'text-muted-foreground',
        )}
        aria-hidden="true"
      />

      <div className={cn('flex flex-col gap-1.5', layout === 'page' && 'items-center')}>
        <p className={cn('font-semibold text-heading', layout === 'page' ? 'text-h2' : 'text-h4')}>
          {headline}
        </p>
        <p className="max-w-[52ch] text-body text-muted-foreground">{body}</p>
      </div>

      {action ? (
        <Button
          variant={severity === 'error' ? 'primary' : 'secondary'}
          size={layout === 'page' ? 'md' : 'sm'}
          onClick={action.onClick}
          loading={action.loading ?? false}
          className={cn(layout === 'page' && 'mt-2')}
        >
          {action.label}
        </Button>
      ) : null}

      {requestId ? (
        <button
          type="button"
          onClick={() => void copy(requestId)}
          className={cn(
            'text-caption text-subtle-foreground hover:text-muted-foreground',
            'mt-2 inline-flex items-center gap-1.5 rounded-sm focus-visible:ring-ring/50',
            'transition-colors focus-visible:ring-[3px] focus-visible:outline-none',
          )}
        >
          <span className="tabular">{requestId}</span>
          {copied ? (
            <Check className="size-3.5" aria-hidden="true" />
          ) : (
            <Copy className="size-3.5" aria-hidden="true" />
          )}
          <span className="sr-only">{copied ? 'Request id copied' : 'Copy request id'}</span>
        </button>
      ) : null}
    </div>
  )
}
