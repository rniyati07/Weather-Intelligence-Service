import { useEffect, useRef } from 'react'

import type { AnyErrorCode, ChatMessage } from '@/types'
import { deriveFollowUpSuggestions, getMessagePlaces } from '@/utils/chat'
import { ChatErrorBanner } from './ChatErrorBanner'
import { EmptyConversation } from './EmptyConversation'
import { FollowUpSuggestions } from './FollowUpSuggestions'
import { MessageBubble } from './MessageBubble'
import { PlaceList } from './PlaceList'
import { TypingIndicator } from './TypingIndicator'

export interface MessageListProps {
  messages: ChatMessage[]
  isSending: boolean
  errorCode: AnyErrorCode | undefined
  onRetry: () => void
  onSelectSuggestion: (text: string) => void
  onPickExample: (text: string) => void
  /** Rendered between the identity header and the transcript — the structured
   * workspace, which belongs to the trip rather than to any one turn. */
  workspace?: React.ReactNode
}

/**
 * The transcript. `role="log"` + `aria-live="polite"` so a new assistant
 * message is announced without stealing focus from the composer.
 *
 * Structured content is composed *around* messages, never inside
 * `MessageBubble`. Trip-level intelligence (outlook, days) mounts once, above
 * the stream, because it describes the trip rather than a turn. Per-turn
 * places stay attached to the turn that returned them — but only when that
 * turn is the latest, so the transcript doesn't accumulate repeated lists as
 * the conversation grows.
 */
export function MessageList({
  messages,
  isSending,
  errorCode,
  onRetry,
  onSelectSuggestion,
  onPickExample,
  workspace,
}: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, isSending])

  if (messages.length === 0 && !isSending) {
    return <EmptyConversation onPick={onPickExample} />
  }

  return (
    <div
      role="log"
      aria-live="polite"
      aria-relevant="additions"
      className="flex min-w-0 flex-1 flex-col gap-6 overflow-y-auto px-5 py-6 md:px-8"
    >
      {workspace}

      {messages.map((message, index) => {
        const isLast = index === messages.length - 1
        const places = isLast && message.role === 'assistant' ? getMessagePlaces(message) : []

        return (
          <div key={message.id} className="flex flex-col gap-4">
            <MessageBubble message={message} />

            {places.length > 0 ? (
              <div className="ml-10 rounded-lg border border-border bg-surface px-4 py-1">
                <PlaceList places={places} />
              </div>
            ) : null}

            {isLast && !isSending && message.role === 'assistant' ? (
              <div className="ml-10">
                <FollowUpSuggestions
                  suggestions={deriveFollowUpSuggestions(message)}
                  onSelect={onSelectSuggestion}
                />
              </div>
            ) : null}
          </div>
        )
      })}

      {isSending ? <TypingIndicator /> : null}

      {!isSending && errorCode ? <ChatErrorBanner code={errorCode} onRetry={onRetry} /> : null}

      <div ref={endRef} />
    </div>
  )
}
