import { MessageSquarePlus, MessagesSquare } from 'lucide-react'
import { Link, NavLink, useParams } from 'react-router'

import { SkeletonText } from '@/components/ui/skeleton'
import { APP_WORDMARK } from '@/constants/app'
import { buildChatPath, ROUTES } from '@/constants/routes'
import { useConversationList } from '@/hooks/queries'
import { cn } from '@/lib/utils'
import { formatRelativeTime } from '@/utils/date'
import { rollingHistoryWindow } from '../active-trip'

/** A conversation's own destination name, or a neutral placeholder while
 * it's still being established — never invents a title. */
function titleFor(tripContext: Record<string, unknown>): string {
  const destination = tripContext.destination
  if (destination && typeof destination === 'object') {
    const name = (destination as Record<string, unknown>).displayName
    if (typeof name === 'string' && name.length > 0) return name
  }
  return 'New conversation'
}

/**
 * The conversation history — server-backed (`GET /conversations`), never a
 * `localStorage` list (master prompt, "Conversation Persistence").
 *
 * One component, two mounting contexts: a permanent column on `md`+ and the
 * content of a slide-in sheet below it — `ChatShell` decides which.
 */
export function ConversationHistoryPanel() {
  const { data, isPending, isError } = useConversationList()
  const { conversationId } = useParams<{ conversationId?: string }>()
  const conversations = data ? rollingHistoryWindow(data, conversationId) : data

  return (
    <nav aria-label="Conversation history" className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-4">
        <Link
          to={ROUTES.home}
          className="flex min-h-11 items-center gap-2 rounded-md focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <span className="text-h4 font-bold">
            <span className="text-heading">{APP_WORDMARK.primary}</span>
            <span className="text-primary">{APP_WORDMARK.secondary}</span>
          </span>
        </Link>
      </div>

      <div className="p-3">
        <Link
          to={ROUTES.home}
          className="flex h-11 items-center justify-center gap-2 rounded-lg border border-border bg-surface text-body font-medium text-foreground transition-colors hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <MessageSquarePlus className="size-4" aria-hidden="true" />
          New conversation
        </Link>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {isPending ? (
          <div className="px-2 py-2">
            <SkeletonText lines={4} />
          </div>
        ) : isError ? (
          <p className="px-3 py-2 text-body-sm text-muted-foreground">
            Couldn’t load your conversations.
          </p>
        ) : !conversations || conversations.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
            <MessagesSquare className="size-6 text-subtle-foreground" aria-hidden="true" />
            <p className="text-body-sm text-muted-foreground">No conversations yet — say hello.</p>
          </div>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {conversations.map((conversation) => (
              <li key={conversation.id}>
                <NavLink
                  to={buildChatPath(conversation.id)}
                  className={({ isActive }) =>
                    cn(
                      'flex flex-col gap-0.5 rounded-md px-3 py-2.5 transition-colors',
                      'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
                      isActive ? 'bg-primary-subtle' : 'hover:bg-muted',
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span
                        className={cn(
                          'truncate text-body-sm font-medium',
                          isActive ? 'text-primary' : 'text-foreground',
                        )}
                      >
                        {titleFor(conversation.tripContext)}
                      </span>
                      {conversation.lastMessagePreview ? (
                        <span className="truncate text-caption text-muted-foreground">
                          {conversation.lastMessagePreview}
                        </span>
                      ) : null}
                      <span className="text-caption text-subtle-foreground">
                        {formatRelativeTime(conversation.updatedAt)}
                      </span>
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-col gap-1 border-t border-border p-3">
        <Link
          to={ROUTES.plan}
          className="rounded-md px-2 py-1.5 text-body-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          Prefer a form? Plan manually →
        </Link>
        <div className="flex items-center gap-1 px-2 text-caption text-subtle-foreground">
          <Link
            to={ROUTES.settings}
            className="rounded-md py-1 hover:text-foreground hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            Settings
          </Link>
          <span aria-hidden="true">·</span>
          <Link
            to={ROUTES.about}
            className="rounded-md py-1 hover:text-foreground hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            About
          </Link>
        </div>
      </div>
    </nav>
  )
}
