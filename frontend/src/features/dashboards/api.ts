import { apiClient } from '@/lib/api-client'
import type { ChartType, Dashboard, DashboardDetail } from '@/types/dashboard'
import type { DatasetQueryRequest } from '@/types/dataset'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

const DASHBOARDS_KEY = ['dashboards'] as const
const dashboardKey = (id: string) => [...DASHBOARDS_KEY, id] as const

export function useDashboards() {
  return useQuery({
    queryKey: DASHBOARDS_KEY,
    queryFn: () => apiClient.get<Dashboard[]>('/dashboards'),
  })
}

export function useDashboard(id: string) {
  return useQuery({
    queryKey: dashboardKey(id),
    queryFn: () => apiClient.get<DashboardDetail>(`/dashboards/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreateDashboard() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => apiClient.post<Dashboard>('/dashboards', { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DASHBOARDS_KEY })
    },
  })
}

export function useDeleteDashboard() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/dashboards/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DASHBOARDS_KEY })
    },
  })
}

interface AddChartPayload {
  dashboardId: string
  datasetId: string
  title: string
  chartType: ChartType
  query: DatasetQueryRequest
}

export function useAddChart() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ dashboardId, datasetId, title, chartType, query }: AddChartPayload) =>
      apiClient.post(`/dashboards/${dashboardId}/charts`, {
        dataset_id: datasetId,
        title,
        chart_type: chartType,
        query,
      }),
    onSuccess: (_data, { dashboardId }) => {
      queryClient.invalidateQueries({ queryKey: dashboardKey(dashboardId) })
      queryClient.invalidateQueries({ queryKey: DASHBOARDS_KEY })
    },
  })
}

export function useDeleteChart(dashboardId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (chartId: string) => apiClient.delete(`/dashboards/${dashboardId}/charts/${chartId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dashboardKey(dashboardId) })
      queryClient.invalidateQueries({ queryKey: DASHBOARDS_KEY })
    },
  })
}

export function useMoveChart(dashboardId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ chartId, direction }: { chartId: string; direction: 'up' | 'down' }) =>
      apiClient.post(`/dashboards/${dashboardId}/charts/${chartId}/move`, { direction }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dashboardKey(dashboardId) })
    },
  })
}
