import { Compass } from 'lucide-react'

// Illustrate how to phrase a message, never a destination — no place name
// belongs here. A picked prompt only fills the composer, but even an
// editable example must not look like a suggested (or worse, remembered)
// trip.
const PROMPTS = [
  'I’m planning a trip and I’m not sure where yet.',
  'Help me pick a destination for next month.',
  'I want a quiet weekend somewhere warm.',
] as const

export interface EmptyConversationProps {
  onPick: (text: string) => void
}

/**
 * The chat entry's welcome state — this *is* the landing page now (master
 * prompt, "Product": "Do NOT create a separate marketing homepage").
 *
 * The example prompts are starting points, not the product: picking one
 * fills the composer rather than sending it immediately, so a first-time
 * visitor can still edit before committing.
 */
export function EmptyConversation({ onPick }: EmptyConversationProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-16 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-ai-surface text-ai-accent">
        <Compass className="size-6" aria-hidden="true" />
      </span>

      <div className="flex flex-col gap-2">
        <h1 className="text-h2 font-bold text-heading">Where are you headed?</h1>
        <p className="max-w-md text-body text-muted-foreground">
          Tell me about your trip — where, when, and what you’re into. I’ll take it from there.
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-2">
        {PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => {
              onPick(prompt)
            }}
            className="inline-flex h-9 items-center rounded-full border border-border bg-surface px-3.5 text-body-sm text-foreground transition-colors duration-150 ease-out hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  )
}
