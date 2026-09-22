import { CloudSun } from 'lucide-react'

/**
 * In-stream loading state while a turn is in flight.
 *
 * Communicates "waiting for a reply", never "receiving one token by token" —
 * there is no partial content to reveal. Chat is one blocking request/
 * response; there is no streaming to simulate (master prompt, "Loading").
 *
 * Deliberately not a speech-bubble with bouncing dots — that pattern reads as
 * "consumer chat app" before a user processes anything else on the page.
 * A quiet label with a hairline progress rule reads as a system computing a
 * result, matching the instrument-panel register the rest of the dashboard
 * keeps.
 */
export function TypingIndicator() {
  return (
    <div className="flex items-center gap-2.5" role="status">
      <span
        className="flex size-6 shrink-0 items-center justify-center rounded-md bg-ai-surface text-ai-accent"
        aria-hidden="true"
      >
        <CloudSun className="size-3.5" />
      </span>

      <p className="text-body-sm text-muted-foreground">
        Computing trip intelligence
        <span className="ml-2 inline-flex h-2 w-16 overflow-hidden rounded-full bg-ai-surface align-middle">
          <span className="h-full w-1/3 animate-[loading-sweep_1.1s_ease-in-out_infinite] rounded-full bg-ai-accent" />
        </span>
        <span className="sr-only"> — planning your trip…</span>
      </p>
    </div>
  )
}
