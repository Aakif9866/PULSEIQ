import { USAGE_KEY } from '@/features/usage/api'
import { apiClient } from '@/lib/api-client'
import type { AnalyzeRequest, AnalyzeResponse, ConversationTurn } from '@/types/analysis'
import type { AskResponse } from '@/types/insight'
import { useMutation, useQueryClient } from '@tanstack/react-query'

/** @deprecated Kept behind VITE_AI_ANALYST_ENGINE=ask (see
 * lib/feature-flags.ts) — superseded by useAnalyzeDataset, which is
 * grounded in real tool calls and validated before being trusted. See
 * docs/AI_ANALYTICS.md's "Deprecated: /ask" note before removing this. */
export function useAskDataset(datasetId: string) {
  return useMutation({
    mutationFn: (question: string) =>
      apiClient.post<AskResponse>(`/datasets/${datasetId}/ask`, { question }),
  })
}

export function useAnalyzeDataset(datasetId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { question: string; conversationHistory?: ConversationTurn[] }) =>
      apiClient.post<AnalyzeResponse>(`/datasets/${datasetId}/analyze`, {
        question: payload.question,
        conversation_history: payload.conversationHistory ?? [],
      } satisfies AnalyzeRequest),
    // Every /analyze call (success or a 429) changes today's usage.
    onSettled: () => queryClient.invalidateQueries({ queryKey: USAGE_KEY }),
  })
}
