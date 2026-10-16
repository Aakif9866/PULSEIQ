import { apiClient } from '@/lib/api-client'
import type { Finding } from '@/types/analysis'
import type { DatasetQueryRequest } from '@/types/dataset'
import type { Insight } from '@/types/insight'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

const INSIGHTS_KEY = ['insights'] as const

export function useInsights() {
  return useQuery({
    queryKey: INSIGHTS_KEY,
    queryFn: () => apiClient.get<Insight[]>('/insights'),
  })
}

export interface SaveInsightPayload {
  datasetId: string
  question: string
  answer: string
  /** Only when the answer came from one structured query (the /ask engine). */
  query?: DatasetQueryRequest
  rowCount?: number
  findings?: Finding[]
}

export function useSaveInsight() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasetId, question, answer, query, rowCount, findings }: SaveInsightPayload) =>
      apiClient.post<Insight>('/insights', {
        dataset_id: datasetId,
        question,
        answer,
        query,
        row_count: rowCount,
        findings,
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
