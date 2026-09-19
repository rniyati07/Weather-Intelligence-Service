import { useMutation, useQueryClient } from '@tanstack/react-query'

import { QUERY_KEYS } from '@/constants/api'
import { sendChatMessage } from '@/services/api'
import type { ChatResponse } from '@/types'

export interface SendChatMessageVariables {
  message: string
  conversationId: string | null
}

/**
 * `POST /conversations/chat` — one blocking turn, no streaming (master
 * prompt, "Loading": "Chat is a blocking request/response flow. There is NO
 * streaming.").
 *
 * Deliberately thin. The optimistic user bubble and the assistant reply built
 * from this mutation's own response both live in `ChatPage`'s local
 * transcript state (`utils/chat.ts`'s `createLocalMessage` /
 * `assistantMessageFromResponse`) rather than here — a mutation hook that
 * also reached into the `['conversation', id]` query cache would need to
 * handle the "this is a brand-new conversation, there is no cache entry yet"
 * case anyway, and `ChatPage` already owns exactly that transition (null id
 * → real id, then a URL navigation). Keeping that logic in one place beat
 * splitting it between a hook and its caller.
 *
 * On success, the history rail's list is invalidated — a new or continued
 * conversation changes its own `updatedAt` / `lastMessagePreview` there too,
 * and refetching that small list is cheap next to a chat turn's own cost.
 */
export function useSendChatMessage() {
  const queryClient = useQueryClient()

  return useMutation<ChatResponse, Error, SendChatMessageVariables>({
    mutationFn: async ({ message, conversationId }) => {
      const result = await sendChatMessage(message, conversationId)
      return result.data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.conversationList() })
    },
  })
}
