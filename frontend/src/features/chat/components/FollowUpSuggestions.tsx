export interface FollowUpSuggestionsProps {
  suggestions: string[]
  onSelect: (text: string) => void
  disabled?: boolean
}

/**
 * Tappable next questions, derived per-turn by `deriveFollowUpSuggestions`
 * (`utils/chat.ts`) — never a fixed set (master prompt, "Follow-Up
 * Suggestions"). Selecting one sends it exactly as if it had been typed.
 */
export function FollowUpSuggestions({
  suggestions,
  onSelect,
  disabled = false,
}: FollowUpSuggestionsProps) {
  if (suggestions.length === 0) return null

  return (
    <div role="group" aria-label="Suggested questions" className="ml-[34px] flex flex-wrap gap-2">
      {suggestions.map((text) => (
        <button
          key={text}
          type="button"
          disabled={disabled}
          onClick={() => {
            onSelect(text)
          }}
          className="inline-flex h-9 items-center rounded-full border border-border bg-surface px-3.5 text-body-sm text-foreground transition-colors duration-150 ease-out hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
        >
          {text}
        </button>
      ))}
    </div>
  )
}
