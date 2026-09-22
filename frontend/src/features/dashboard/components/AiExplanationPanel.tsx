import { CloudSun, RefreshCw } from 'lucide-react'
import { useState } from 'react'

import { ErrorState } from '@/components/feedback/ErrorState'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { SkeletonText } from '@/components/ui/skeleton'
import { AI_DISCLOSURE, AI_PANEL_TITLE } from '@/constants/app'
import { getErrorPresentation } from '@/constants/error-copy'
import type { Narrative } from '@/types'
import { cn } from '@/lib/utils'

export type NarrativeStatus = 'idle' | 'loading' | 'ready' | 'failed'

export interface AiExplanationPanelProps {
  status: NarrativeStatus
  narrative: Narrative | null
  onRetry: () => void
  /** Dev affordance for exercising the degraded path. Removed with the mock. */
  onPreviewFailure?: () => void
}

/**
 * AI Explanation — FDS §6.4, §7.2.
 *
 * The single most important integration rule in the design lives here.
 * Narration is mandatory *server-side* (the Phase 8 refactor removed the
 * templated fallback), so an LLM failure returns `503 SERVICE_DEGRADED`. But it
 * is **optional to the user experience**: it is fetched in parallel, rendered
 * late, and when it fails the error stays inside this card while the verdict,
 * timeline and packing list remain fully rendered and interactive.
 *
 * Three further rules, all mandatory:
 *
 *  · Titled "AI Explanation". Never "advice", "advisor" or "recommendation" —
 *    the product must not imply the model formed a judgement (ADR-005/010).
 *  · Visually distinct (insight-gold surface, AI glyph) so a user can tell
 *    generated text from computed data without reading the label.
 *  · **Nothing here is ever parsed for a value.** Every number on this page
 *    comes from the structured payload; this text only restates them.
 */
export function AiExplanationPanel({
  status,
  narrative,
  onRetry,
  onPreviewFailure,
}: AiExplanationPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const failure = getErrorPresentation('SERVICE_DEGRADED')

  return (
    <Card variant="ai" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2.5 text-h3 font-semibold text-heading">
          <CloudSun className="size-5 text-ai-accent" aria-hidden="true" />
          {AI_PANEL_TITLE}
        </h2>

        <div className="flex flex-wrap items-center gap-1">
          {status === 'ready' && narrative?.modelUsed ? (
            <p className="mr-2 text-body-sm text-muted-foreground">
              Explained by {narrative.modelUsed}
            </p>
          ) : null}

          {status === 'ready' ? (
            <Button variant="ghost" size="sm" onClick={onRetry}>
              <RefreshCw aria-hidden="true" />
              Regenerate
            </Button>
          ) : null}

          {onPreviewFailure && status === 'ready' ? (
            <Button variant="ghost" size="sm" onClick={onPreviewFailure}>
              Preview failure state
            </Button>
          ) : null}
        </div>
      </div>

      {/* `aria-live="polite"`: narration arrives 6–8s after the deterministic
          content, so its arrival is announced without stealing focus from
          whatever the user is already reading (FDS §14.3). */}
      <div aria-live="polite" aria-busy={status === 'loading'}>
        {status === 'loading' ? (
          <div className="flex flex-col gap-3">
            <SkeletonText lines={4} />
            {/* Names what is happening, so the skeleton doesn't read as an
                unfinished page while the rest of the dashboard is complete. */}
            <p className="text-body-sm text-muted-foreground">Generating explanation…</p>
          </div>
        ) : null}

        {status === 'failed' ? (
          <ErrorState
            layout="inline"
            severity="muted"
            headline={failure.headline}
            body={failure.body}
            action={{ label: failure.action ?? 'Try again', onClick: onRetry }}
            className="bg-transparent px-0 py-0"
          />
        ) : null}

        {status === 'idle' ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-body text-muted-foreground">
              See a plain-language summary of this trip&rsquo;s intelligence.
            </p>
            <Button variant="secondary" size="sm" onClick={onRetry}>
              <CloudSun aria-hidden="true" />
              Generate explanation
            </Button>
          </div>
        ) : null}

        {status === 'ready' && narrative ? (
          <>
            <p
              className={cn(
                'text-body-lg text-ai-foreground',
                // Clamped on mobile with a "Read more" — this is prose, and four
                // lines is enough to decide whether to read the rest.
                !expanded && 'line-clamp-4 md:line-clamp-none',
              )}
            >
              {narrative.summaryText}
            </p>

            <Button
              variant="link"
              size="sm"
              className="mt-1 px-0 md:hidden"
              onClick={() => {
                setExpanded((open) => !open)
              }}
              aria-expanded={expanded}
            >
              {expanded ? 'Show less' : 'Read more'}
            </Button>
          </>
        ) : null}
      </div>

      {status === 'ready' ? (
        <p className="border-t border-ai-border pt-4 text-body-sm text-muted-foreground">
          {AI_DISCLOSURE}
        </p>
      ) : null}
    </Card>
  )
}
