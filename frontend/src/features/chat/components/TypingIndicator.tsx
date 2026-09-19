import { Sparkles } from 'lucide-react'

/**
 * In-stream loading state while a turn is in flight.
 *
 * Communicates "waiting for a reply", never "receiving one token by token" —
 * there is no partial content to reveal. Chat is one blocking request/
 * response; there is no streaming to simulate (master prompt, "Loading").
 */
export function TypingIndicator() {
  return (
    <div className="flex items-start gap-2.5" role="status">
      <span
        className="mt-1 flex size-6 shrink-0 items-center justify-center rounded-full bg-ai-surface text-ai-accent"
        aria-hidden="true"
      >
        <Sparkles className="size-3.5" />
      </span>

      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm border border-ai-border bg-ai-surface px-4 py-3.5">
        <span className="size-1.5 animate-bounce rounded-full bg-ai-accent [animation-delay:-0.3s]" />
        <span className="size-1.5 animate-bounce rounded-full bg-ai-accent [animation-delay:-0.15s]" />
        <span className="size-1.5 animate-bounce rounded-full bg-ai-accent" />
        <span className="sr-only">Planning your trip…</span>
      </div>
    </div>
  )
}
