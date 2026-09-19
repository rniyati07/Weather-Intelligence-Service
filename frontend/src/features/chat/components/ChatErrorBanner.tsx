import { AlertCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { getErrorPresentation } from '@/constants/error-copy'
import type { AnyErrorCode } from '@/types'

export interface ChatErrorBannerProps {
  code: AnyErrorCode | undefined
  onRetry: () => void
}

/**
 * A failed *turn* — an HTTP-layer failure on `POST /conversations/chat`
 * (401/404/429/500/network), not an LLM failure. The backend absorbs an LLM
 * failure into a normal `200` with a deterministic fallback (FDS Revision 2
 * §0.1, §13.3); this banner exists only for the failures that actually
 * reach the frontend as failures.
 *
 * Scoped to the turn: the transcript above stays intact, the composer stays
 * usable, and retrying resends the same message rather than the thread
 * having to restart (master prompt, "Error Handling").
 */
export function ChatErrorBanner({ code, onRetry }: ChatErrorBannerProps) {
  const presentation = getErrorPresentation(code)

  return (
    <div
      role="alert"
      className="ml-[34px] flex flex-wrap items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-body-sm"
    >
      <AlertCircle className="size-4 shrink-0 text-destructive" aria-hidden="true" />
      <p className="text-foreground">
        <span className="font-medium">{presentation.headline}.</span> {presentation.body}
      </p>
      <Button variant="ghost" size="sm" onClick={onRetry} className="ml-auto shrink-0">
        {presentation.action ?? 'Try again'}
      </Button>
    </div>
  )
}
