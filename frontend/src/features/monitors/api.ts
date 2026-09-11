import { apiClient } from '@/lib/api-client'
import type { Anomaly, Monitor, MonitorCreate, MonitorRunResult, MonitorUpdate } from '@/types/monitor'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

const MONITORS_KEY = ['monitors'] as const
const monitorKey = (id: string) => [...MONITORS_KEY, id] as const
const anomaliesKey = (monitorId?: string) =>
  monitorId ? (['anomalies', monitorId] as const) : (['anomalies'] as const)

export function useMonitors() {
  return useQuery({
    queryKey: MONITORS_KEY,
    queryFn: () => apiClient.get<Monitor[]>('/monitors'),
  })
}

export function useMonitor(id: string) {
  return useQuery({
    queryKey: monitorKey(id),
    queryFn: () => apiClient.get<Monitor>(`/monitors/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreateMonitor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: MonitorCreate) => apiClient.post<Monitor>('/monitors', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MONITORS_KEY })
    },
  })
}

export function useUpdateMonitor(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: MonitorUpdate) => apiClient.patch<Monitor>(`/monitors/${id}`, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MONITORS_KEY })
      queryClient.invalidateQueries({ queryKey: monitorKey(id) })
    },
  })
}

export function useDeleteMonitor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/monitors/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MONITORS_KEY })
    },
  })
}

export function useRunMonitor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.post<MonitorRunResult>(`/monitors/${id}/run`),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: MONITORS_KEY })
      queryClient.invalidateQueries({ queryKey: monitorKey(id) })
      queryClient.invalidateQueries({ queryKey: anomaliesKey() })
      queryClient.invalidateQueries({ queryKey: anomaliesKey(id) })
    },
  })
}

export function useAnomalies(monitorId?: string) {
  return useQuery({
    queryKey: anomaliesKey(monitorId),
    queryFn: () =>
      apiClient.get<Anomaly[]>(
        monitorId ? `/monitors/anomalies?monitor_id=${monitorId}` : '/monitors/anomalies',
      ),
  })
}
