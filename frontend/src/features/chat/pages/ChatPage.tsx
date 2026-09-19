import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'

import { LoadingSkeleton } from '@/components/feedback/LoadingSkeleton'
import { Button } from '@/components/ui/button'
import { buildChatPath, ROUTES } from '@/constants/routes'
import { useConversationThread, useSendChatMessage, useTripIntelligence } from '@/hooks/queries'
import { ApiError } from '@/services/api'
import type { ChatMessage, IsoDate } from '@/types'
import { parseTripContext } from '@/types'
import {
  assistantMessageFromResponse,
  createLocalMessage,
  latestPlaces,
  latestTripContext,
} from '@/utils/chat'
import { isActiveTrip, tripIdentity, tripLocationId } from '../active-trip'
import { ChatComposer } from '../components/ChatComposer'
import { ChatShell } from '../components/ChatShell'
import { IntelligenceSidebar } from '../components/IntelligenceSidebar'
import { MessageList } from '../components/MessageList'
import { TripIdentityHeader } from '../components/TripIdentityHeader'
import { TripWorkspacePanel } from '../components/TripWorkspacePanel'

/**
 * The product — `/` (new conversation) and `/chat/:conversationId` (an
 * active one). Chat-first: this page opens directly into the conversation,
 * with the structured trip workspace composed around it once the backend has
 * resolved enough of the trip to compute anything.
 *
 * `key={conversationId ?? 'new'}` on {@link ChatConversation} is the whole
 * state-reset strategy: switching conversations remounts it, giving every
 * piece of local transcript state a fresh start — React's own guidance
 * ("resetting state when a prop changes") prefers a `key` over an effect for
 * exactly this, and this codebase's lint config forbids `setState` inside
 * `useEffect` bodies entirely.
 */
export function ChatPage() {
  const { conversationId: routeConversationId } = useParams<{ conversationId?: string }>()
  const conversationId = routeConversationId ?? null

  return <ChatConversation key={conversationId ?? 'new'} conversationId={conversationId} />
}

interface ChatNavigationState {
  /** Carries the just-sent exchange across the id transition when a brand
   * new conversation gets its first real id — see `performSend` below. */
  seedMessages?: ChatMessage[]
}

function ChatConversation({ conversationId }: { conversationId: string | null }) {
  const navigate = useNavigate()
  const location = useLocation()
  const seedFromNavigation = (location.state as ChatNavigationState | null)?.seedMessages

  // Turns sent or received *this session*, beyond whatever `thread` last
  // fetched. No effect needed to reconcile the two: once this holds anything,
  // `thread` is disabled below, so the server snapshot it already has is
  // frozen and `[...serverMessages, ...localExtra]` can never duplicate or
  // drop a turn.
  const [localExtra, setLocalExtra] = useState<ChatMessage[]>(() => seedFromNavigation ?? [])
  const threadEnabled = conversationId !== null && localExtra.length === 0
  const thread = useConversationThread(threadEnabled ? conversationId : null)
  const sendMessage = useSendChatMessage()

  const [draft, setDraft] = useState('')
  const [selectedDate, setSelectedDate] = useState<IsoDate | null>(null)

  const messages = [...(thread.data?.messages ?? []), ...localExtra]

  // The trip as the backend last described it: the freshest `tripContext` any
  // turn carried, falling back to the conversation's own stored context when
  // the thread was restored from `GET /conversations/{id}` (whose messages
  // carry no per-turn extras).
  const trip = latestTripContext(messages) ?? parseTripContext(thread.data?.tripContext)

  // The workspace is a property of the *trip*, never of the latest turn's
  // intent — a packing or weather question must not tear it down. It does
  // wait for the first assistant reply, so a new conversation stays
  // conversation-first until the backend has actually answered something.
  const hasAssistantReply = messages.some((message) => message.role === 'assistant')
  const activeTrip = isActiveTrip(trip, hasAssistantReply)
  const places = latestPlaces(messages, tripIdentity(trip))

  // One query for both the workspace panel and the sidebar, so the two can
  // never disagree about a number or a day.
  const tripIntelligence = useTripIntelligence(trip)
  const intelligence = tripIntelligence.data?.data ?? null

  async function performSend(text: string, appendUserBubble: boolean) {
    const optimisticUser = appendUserBubble
      ? createLocalMessage(conversationId ?? '', 'user', text)
      : null
    if (optimisticUser) {
      setLocalExtra((current) => [...current, optimisticUser])
    }
    sendMessage.reset()

    try {
      const response = await sendMessage.mutateAsync({ message: text, conversationId })
      const assistantMessage = assistantMessageFromResponse(response)
      setLocalExtra((current) => [...current, assistantMessage])

      if (!conversationId) {
        const priorLocal = optimisticUser ? [...localExtra, optimisticUser] : localExtra
        const seedMessages = [...(thread.data?.messages ?? []), ...priorLocal, assistantMessage]
        void navigate(buildChatPath(response.conversationId), {
          replace: true,
          state: { seedMessages } satisfies ChatNavigationState,
        })
      }
    } catch {
      // The optimistic user bubble (if any) stays via `localExtra` — the turn
      // failed, not the conversation. `ChatErrorBanner` offers a retry of the
      // same text without re-adding it.
    }
  }

  function submit(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return
    setDraft('')
    void performSend(trimmed, true)
  }

  function retry() {
    const lastUser = [...messages].reverse().find((message) => message.role === 'user')
    if (lastUser) void performSend(lastUser.content, false)
  }

  // A cold load, still in flight — never shown once anything local exists, so
  // this never flashes over an active session.
  if (conversationId && thread.isPending && localExtra.length === 0) {
    return (
      <ChatShell>
        <div className="flex-1 px-5 py-6 md:px-8">
          <LoadingSkeleton variant="card" count={3} label="Loading conversation" />
        </div>
      </ChatShell>
    )
  }

  // A cold load that did not resolve — same guard: never shown once a
  // transcript already exists, so a transient background error on an active
  // conversation cannot blank it.
  if (conversationId && thread.isError && localExtra.length === 0) {
    return (
      <ChatShell>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-4 text-center">
          <p className="text-h3 font-semibold text-heading">This conversation could not be found</p>
          <p className="max-w-sm text-body text-muted-foreground">
            It may have been removed. Start a new one below.
          </p>
          <Button asChild>
            <Link to={ROUTES.home}>Start a new conversation</Link>
          </Button>
        </div>
      </ChatShell>
    )
  }

  const errorCode =
    sendMessage.isError && ApiError.is(sendMessage.error) ? sendMessage.error.code : undefined

  const glanceDay =
    intelligence?.dailyIntelligence.find((day) => day.date === selectedDate) ??
    intelligence?.dailyIntelligence[0]

  // Mounted for the whole life of the active trip. Its subsections each
  // handle their own absence, so a failed places lookup or a still-loading
  // intelligence query narrows the layer rather than removing it.
  const sidebar = activeTrip ? (
    <IntelligenceSidebar
      destinationName={trip.destination?.name ?? ''}
      glanceDay={glanceDay}
      summary={intelligence?.tripSummary}
      places={places}
      interests={trip.interests ?? []}
      isPending={tripIntelligence.isPending}
      isError={tripIntelligence.isError}
    />
  ) : null

  const locationId = tripLocationId(trip)

  return (
    <ChatShell header={activeTrip ? <TripIdentityHeader trip={trip} /> : null} sidebar={sidebar}>
      <MessageList
        messages={messages}
        isSending={sendMessage.isPending}
        errorCode={errorCode}
        onRetry={retry}
        onSelectSuggestion={submit}
        onPickExample={setDraft}
        workspace={
          activeTrip && locationId && trip.startDate && trip.endDate ? (
            <TripWorkspacePanel
              intelligence={intelligence}
              isPending={tripIntelligence.isPending}
              isError={tripIntelligence.isError}
              onRetry={tripIntelligence.refetch}
              locationId={locationId}
              startDate={trip.startDate}
              endDate={trip.endDate}
              selectedDate={selectedDate}
              onSelectDate={setSelectedDate}
            />
          ) : null
        }
      />
      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSubmit={() => {
          submit(draft)
        }}
        disabled={sendMessage.isPending}
        // The invitation belongs on an empty conversation; once a trip is
        // running the shorter prompt keeps the composer to one line.
        placeholder={
          messages.length === 0
            ? 'Tell me about your trip — where, when, and what you’re into.'
            : undefined
        }
      />
    </ChatShell>
  )
}
