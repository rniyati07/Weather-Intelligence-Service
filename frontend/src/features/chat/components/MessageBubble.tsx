import { Sparkles } from 'lucide-react'

import type { ChatMessage } from '@/types'
import { getMessageLlmGenerated } from '@/utils/chat'
import { renderMessageText } from '@/utils/markdown'

export interface MessageBubbleProps {
  message: ChatMessage
}

/**
 * One conversation turn.
 *
 * Renders `message.content` and nothing else — no parsing, no fact
 * extraction, no derived labels. Every structured element that accompanies a
 * reply (trip outlook, day strip, places) is a sibling in the workspace,
 * never derived from this component.
 *
 * The assistant turn is deliberately *not* a tinted, bordered container: a
 * reply is the page's primary reading, and wrapping every one in a coloured
 * card made long answers overwhelming and turned the transcript into a stack
 * of boxes. The AI cue is carried by the small avatar and the byline instead,
 * which is enough to tell generated prose from computed panels at a glance.
 * The user turn keeps a compact bubble, since it needs to read as an aside.
 */
export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-xl rounded-br-sm border border-border bg-surface px-4 py-2.5 text-body text-foreground md:max-w-[75%]">
          {renderMessageText(message.content)}
        </div>
      </div>
    )
  }

  const llmGenerated = getMessageLlmGenerated(message)

  return (
    <div className="flex items-start gap-3">
      <span
        className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-ai-surface text-ai-accent"
        aria-hidden="true"
      >
        <Sparkles className="size-3.5" />
      </span>

      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-body-sm">
          <span className="font-semibold text-heading">Weather Intelligence</span>
          {/* Only rendered when the field says so, never inferred from the
              text (master prompt, "LLM Generated State"). Quiet, not an
              error — chat degrades to a deterministic summary server-side
              rather than failing (FDS Revision 2 §13.3). */}
          {llmGenerated === false ? (
            <span className="text-caption text-subtle-foreground">Structured summary</span>
          ) : null}
        </p>

        <div className="mt-1.5 max-w-[68ch] text-body text-foreground [&_p+p]:mt-3 [&_strong]:font-semibold [&_strong]:text-heading">
          {renderMessageText(message.content)}
        </div>
      </div>
    </div>
  )
}
