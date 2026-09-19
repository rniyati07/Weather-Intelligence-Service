import { ArrowUp } from 'lucide-react'
import { useRef, type FormEvent, type KeyboardEvent } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const MAX_MESSAGE_LENGTH = 4000
const MAX_TEXTAREA_HEIGHT_PX = 200

export interface ChatComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  disabled?: boolean
  placeholder?: string | undefined
}

/**
 * Message input. Sticky to the viewport bottom inside `ChatShell`'s flex
 * column, with `env(safe-area-inset-bottom)` so it clears a phone's home
 * indicator (master prompt, "390px: sticky keyboard-safe composer").
 *
 * Enter sends; Shift+Enter inserts a newline. The textarea grows with
 * content up to a cap rather than scrolling internally too early.
 */
export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholder,
}: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function autoResize(element: HTMLTextAreaElement) {
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, MAX_TEXTAREA_HEIGHT_PX).toString()}px`
  }

  function handleInput(event: FormEvent<HTMLTextAreaElement>) {
    onChange(event.currentTarget.value)
    autoResize(event.currentTarget)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  function submit() {
    if (disabled || value.trim().length === 0) return
    onSubmit()
    requestAnimationFrame(() => {
      const el = textareaRef.current
      if (el) {
        el.style.height = 'auto'
      }
    })
  }

  const canSend = value.trim().length > 0 && !disabled

  return (
    <form
      className={cn(
        'flex items-end gap-2 border-t border-border bg-background/95 p-3 backdrop-blur-md md:p-4',
        'pb-[max(0.75rem,env(safe-area-inset-bottom))]',
      )}
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <label htmlFor="chat-composer-input" className="sr-only">
        Message
      </label>
      <textarea
        ref={textareaRef}
        id="chat-composer-input"
        value={value}
        onInput={handleInput}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={1}
        maxLength={MAX_MESSAGE_LENGTH}
        placeholder={placeholder ?? 'Ask about your trip…'}
        className={cn(
          // `field-sizing-content` lets the box track its own text, and the
          // explicit row height stops a wrapped placeholder being clipped at
          // 390px, where the placeholder runs to two lines.
          'max-h-[200px] min-h-12 flex-1 resize-none rounded-lg border border-input bg-surface px-3.5 py-3',
          'text-body text-foreground placeholder:text-subtle-foreground',
          'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
          'disabled:opacity-60',
        )}
      />
      <Button
        type="submit"
        size="icon"
        disabled={!canSend}
        loading={disabled}
        aria-label="Send message"
      >
        <ArrowUp aria-hidden="true" />
      </Button>
    </form>
  )
}
