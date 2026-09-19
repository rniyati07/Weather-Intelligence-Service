import { useQuery } from '@tanstack/react-query'

import { QUERY_CACHE, QUERY_KEYS } from '@/constants/api'
import { getConversation } from '@/services/api'
import type { Conversation } from '@/types'
import { toQueryResult } from './to-query-result'
import type { QueryResult } from './types'

/**
 * `GET /conversations/{id}` — restores a thread on direct navigation or
 * refresh (master prompt, "Conversation Persistence").
 *
 * `staleTime: 0` means this always refetches on mount/navigation rather than
 * trusting a cached copy — a conversation is mutated by the chat endpoint,
 * which this hook never touches, so a stale read would silently miss turns
 * sent from elsewhere (another tab, a resumed session).
 *
 * Once loaded, `ChatPage` seeds its own local transcript from this result
 * and stops reading it — the active session's own optimistic/confirmed
 * turns become authoritative for rendering from then on (see
 * `useSendChatMessage`'s module comment for why).
 */
export function useConversationThread(conversationId: string | null): QueryResult<Conversation> {
  const enabled = Boolean(conversationId)

  const query = useQuery({
    queryKey: QUERY_KEYS.conversation(conversationId ?? ''),
    queryFn: async ({ signal }) => {
      const result = await getConversation(conversationId ?? '', signal)
      return result.data
    },
    enabled,
    ...QUERY_CACHE.conversation,
  })

  return toQueryResult(query, enabled)
}
