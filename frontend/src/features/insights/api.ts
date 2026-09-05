import { apiClient } from '@/lib/api-client'
import type { AskResponse, Insight } from '@/types/insight'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

const INSIGHTS_KEY = ['insights'] as const

export function useInsights() {
  return useQuery({
    queryKey: INSIGHTS_KEY,
    queryFn: () => apiClient.get<Insight[]>('/insights'),
  })
}

interface SaveInsightPayload {
  datasetId: string
  ask: AskResponse
}

export function useSaveInsight() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasetId, ask }: SaveInsightPayload) =>
      apiClient.post<Insight>('/insights', {
        dataset_id: datasetId,
        question: ask.question,
        answer: ask.answer,
        query: ask.query,
        row_count: ask.result.row_count,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: INSIGHTS_KEY })
    },
  })
}

export function useDeleteInsight() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/insights/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: INSIGHTS_KEY })
    },
  })
}
