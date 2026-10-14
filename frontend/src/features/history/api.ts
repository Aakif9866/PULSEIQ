import { apiClient } from '@/lib/api-client'
import type {
  AskSqlResponse,
  QueryHistoryItem,
  RunSqlResponse,
  SavedQuery,
  SuggestedQuery,
} from '@/types/history'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

const historyKey = (datasetId: string) => ['history', datasetId] as const
const savedKey = (datasetId: string) => ['saved-queries', datasetId] as const

export function useSuggestedQueries(datasetId: string) {
  return useQuery({
    queryKey: ['suggested-queries', datasetId],
    queryFn: () => apiClient.get<SuggestedQuery[]>(`/datasets/${datasetId}/suggested-queries`),
    enabled: Boolean(datasetId),
  })
}

export function useQueryHistory(datasetId: string) {
  return useQuery({
    queryKey: historyKey(datasetId),
    queryFn: () => apiClient.get<QueryHistoryItem[]>(`/history?dataset_id=${datasetId}`),
    enabled: Boolean(datasetId),
  })
}

export function useSavedQueries(datasetId: string) {
  return useQuery({
    queryKey: savedKey(datasetId),
    queryFn: () => apiClient.get<SavedQuery[]>(`/queries?dataset_id=${datasetId}`),
    enabled: Boolean(datasetId),
  })
}

/** Both SQL paths write a history row server-side, so refresh it after. */
export function useRunSql(datasetId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (sql: string) =>
      apiClient.post<RunSqlResponse>(`/datasets/${datasetId}/sql`, { sql }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: historyKey(datasetId) }),
  })
}

export function useAskSql(datasetId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (question: string) =>
      apiClient.post<AskSqlResponse>(`/datasets/${datasetId}/ask-sql`, { question }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: historyKey(datasetId) }),
  })
}

export function useSaveQuery(datasetId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; sql_text: string }) =>
      apiClient.post<SavedQuery>('/queries', { dataset_id: datasetId, ...body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: savedKey(datasetId) }),
  })
}

export function useDeleteSavedQuery(datasetId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/queries/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: savedKey(datasetId) }),
  })
}
