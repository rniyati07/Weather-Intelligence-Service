/**
 * Conversation and chat requests — the primary product surface.
 *
 * Same rules as `endpoints.ts`: one function per endpoint, `ApiResult<T>`
 * out, nothing caught here (the response interceptor already normalises
 * every failure to a typed `ApiError`). No React, no caching — that is
 * `hooks/queries`'s job.
 */

import { ENDPOINTS } from '@/constants/api'
import type {
  ApiEnvelope,
  ApiResult,
  ChatResponse,
  Conversation,
  ConversationSummary,
} from '@/types'

import { apiClient, unwrap } from './client'

/** `POST /conversations` — starts an empty conversation, or one with an
 * opening message already attached. Not required for the primary flow:
 * `sendChatMessage` with `conversationId: null` creates one implicitly. */
export async function createConversation(
  initialMessage?: string,
): Promise<ApiResult<{ conversation: Conversation }>> {
  const response = await apiClient.post<ApiEnvelope<{ conversation: Conversation }>>(
    ENDPOINTS.conversations(),
    initialMessage ? { initialMessage } : {},
  )
  return unwrap(response)
}

/** `GET /conversations` — populates the history rail. */
export async function listConversations(
  signal?: AbortSignal,
): Promise<ApiResult<ConversationSummary[]>> {
  const response = await apiClient.get<ApiEnvelope<ConversationSummary[]>>(
    ENDPOINTS.conversations(),
    signal ? { signal } : {},
  )
  return unwrap(response)
}

/** `GET /conversations/{id}` — restores a thread on direct navigation or refresh. */
export async function getConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ApiResult<Conversation>> {
  const response = await apiClient.get<ApiEnvelope<Conversation>>(
    ENDPOINTS.conversation(conversationId),
    signal ? { signal } : {},
  )
  return unwrap(response)
}

/**
 * `POST /conversations/chat` — one turn in, one turn out. Blocking; there is
 * no streaming to model here (master prompt, "Loading").
 */
export async function sendChatMessage(
  message: string,
  conversationId: string | null,
): Promise<ApiResult<ChatResponse>> {
  const response = await apiClient.post<ApiEnvelope<ChatResponse>>(ENDPOINTS.chat(), {
    message,
    conversationId,
  })
  return unwrap(response)
}
