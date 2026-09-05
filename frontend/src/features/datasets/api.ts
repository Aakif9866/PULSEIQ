import { apiClient } from '@/lib/api-client'
import type { Dataset, DatasetQueryRequest, DatasetQueryResult } from '@/types/dataset'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

const DATASETS_KEY = ['datasets'] as const
const datasetKey = (id: string) => [...DATASETS_KEY, id] as const

export function useDatasets() {
  return useQuery({
    queryKey: DATASETS_KEY,
    queryFn: () => apiClient.get<Dataset[]>('/datasets'),
  })
}

export function useDataset(id: string) {
  return useQuery({
    queryKey: datasetKey(id),
    queryFn: () => apiClient.get<Dataset>(`/datasets/${id}`),
    enabled: Boolean(id),
  })
}

export function useUploadDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return apiClient.upload<Dataset>('/datasets', formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DATASETS_KEY })
    },
  })
}

export function useDeleteDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/datasets/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DATASETS_KEY })
    },
  })
}

/** Which storage backend is actually active — so UI copy about
 * persistence reflects reality instead of a hardcoded assumption. */
export function useStorageMode() {
  return useQuery({
    queryKey: ['storage-mode'],
    queryFn: () =>
      apiClient.get<{ status: string; storage_provider: 'local' | 'r2' }>('/health', {
        auth: false,
      }),
    staleTime: Infinity,
  })
}

export function useRunDatasetQuery(datasetId: string) {
  return useMutation({
    mutationFn: (request: DatasetQueryRequest) =>
      apiClient.post<DatasetQueryResult>(`/datasets/${datasetId}/query`, request),
  })
}

/** Auto-fetching counterpart to useRunDatasetQuery, for a query that's
 * already decided (e.g. a saved dashboard chart) rather than user-triggered. */
export function useDatasetQueryResult(datasetId: string, request: DatasetQueryRequest) {
  return useQuery({
    queryKey: [...datasetKey(datasetId), 'query', request],
    queryFn: () => apiClient.post<DatasetQueryResult>(`/datasets/${datasetId}/query`, request),
    enabled: Boolean(datasetId),
  })
}
