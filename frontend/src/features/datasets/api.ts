import { apiClient } from '@/lib/api-client'
import type { Dataset, DatasetQueryRequest, DatasetQueryResult, DatasetVersion, VersionUploadResult } from '@/types/dataset'
import type { DatasetBriefing } from '@/types/briefing'
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

/** Deterministic overview + suggested questions (no AI quota). */
export function useDatasetBriefing(id: string, enabled = true) {
  return useQuery({
    queryKey: ['dataset-briefing', id],
    queryFn: () => apiClient.get<DatasetBriefing>(`/datasets/${id}/briefing`),
    enabled: Boolean(id) && enabled,
    staleTime: 5 * 60_000, // a dataset's contents never change after upload
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

export function useDatasetVersions(id: string) {
  return useQuery({
    queryKey: ['dataset-versions', id],
    queryFn: () => apiClient.get<DatasetVersion[]>(`/datasets/${id}/versions`),
    enabled: Boolean(id),
  })
}

/** Uploads a new file over a dataset. Everything computed from the old
 * data (briefing, queries, insights' staleness, checks) refreshes. */
export function useUploadVersion(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return apiClient.upload<VersionUploadResult>(`/datasets/${id}/versions`, formData)
    },
    onSuccess: () => {
      // DATASETS_KEY also covers this dataset's cached query results.
      for (const key of [DATASETS_KEY, ['dataset-briefing', id], ['dataset-versions', id],
        ['insights'], ['monitors']]) {
        queryClient.invalidateQueries({ queryKey: key })
      }
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
      apiClient.get<{
        status: string
        storage_provider: 'local' | 'r2'
        max_upload_size_mb: number
        max_datasets_per_user: number
        email_alerts_enabled: boolean
      }>('/health', {
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

export function usePublicStats() {
  return useQuery({
    queryKey: ['public-stats'],
    queryFn: () => apiClient.get<{ total_users: number }>('/stats', { auth: false }),
  })
}
