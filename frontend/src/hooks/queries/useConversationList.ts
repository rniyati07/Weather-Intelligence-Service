import { useQuery } from '@tanstack/react-query'

import { QUERY_CACHE, QUERY_KEYS } from '@/constants/api'
import { listConversations } from '@/services/api'
import type { ConversationSummary } from '@/types'
import { toQueryResult } from './to-query-result'
import type { QueryResult } from './types'

/**
 * `GET /conversations` — the history rail. Real, server-backed state, not a
 * `localStorage` list (master prompt, "Conversation Persistence").
 */
export function useConversationList(): QueryResult<ConversationSummary[]> {
  const query = useQuery({
    queryKey: QUERY_KEYS.conversationList(),
    queryFn: async ({ signal }) => {
      const result = await listConversations(signal)
      return result.data
    },
    ...QUERY_CACHE.conversationList,
  })

  return toQueryResult(query)
}
