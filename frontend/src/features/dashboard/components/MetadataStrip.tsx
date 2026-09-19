import { Check, Copy, Info } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Tooltip } from '@/components/ui/tooltip'
import { useCopyToClipboard } from '@/hooks/useCopyToClipboard'
import type { ResponseMetadata } from '@/types'
import { formatAbsoluteTime, formatRelativeTime } from '@/utils/date'

export interface MetadataStripProps {
  metadata: ResponseMetadata
}

/**
 * Quiet provenance — FDS §6.5, §8.1.
 *
 * Two judgements encoded here.
 *
 * First, `cacheStatus` of `hit` or `miss` is **silent**. Neither tells a
 * traveller anything actionable, and surfacing them would train people to
 * ignore this strip — which matters, because `stale` genuinely does need to be
 * read.
 *
 * Second, stale or degraded data is **not an error**. It renders as a neutral
 * informational badge with the full analysis intact beneath it, never in red.
 * The product degrades visibly but calmly (FDS §13.4).
 */
export function MetadataStrip({ metadata }: MetadataStripProps) {
  const { copied, copy } = useCopyToClipboard()

  const isStale = metadata.cacheStatus === 'stale' || metadata.degraded === true

  return (
    <div className="mt-12 flex flex-wrap items-center justify-between gap-x-4 gap-y-3 border-t border-border pt-6">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-body-sm text-muted-foreground">
        <Tooltip content={formatAbsoluteTime(metadata.generatedAt)}>
          <span
            tabIndex={0}
            className="rounded-sm focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            Updated {formatRelativeTime(metadata.generatedAt)}
          </span>
        </Tooltip>

        {metadata.ruleConfigVersion ? (
          <>
            <Separator />
            <span className="tabular">rules {metadata.ruleConfigVersion}</span>
          </>
        ) : null}

        {isStale ? (
          <>
            <Separator />
            <Badge variant="outline" icon={<Info />}>
              Showing last available data
            </Badge>
          </>
        ) : null}
      </div>

      {/* The support affordance: a user quoting this id is the reason it is on
          screen at all. Hidden below `md`, where it is available in Settings. */}
      <button
        type="button"
        onClick={() => {
          void copy(metadata.requestId)
        }}
        className="hidden min-h-8 items-center gap-1.5 rounded-sm text-caption text-subtle-foreground transition-colors hover:text-muted-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none md:inline-flex"
      >
        <span className="tabular">{metadata.requestId}</span>
        {copied ? (
          <Check className="size-3.5" aria-hidden="true" />
        ) : (
          <Copy className="size-3.5" aria-hidden="true" />
        )}
        <span className="sr-only">{copied ? 'Request id copied' : 'Copy request id'}</span>
      </button>
    </div>
  )
}

function Separator() {
  return (
    <span aria-hidden="true" className="text-border-strong">
      ·
    </span>
  )
}
