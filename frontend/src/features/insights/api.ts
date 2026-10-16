import { apiClient } from '@/lib/api-client'
import type { Finding, ToolCallRecord } from '@/types/analysis'
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
  title?: string
  toolCalls?: ToolCallRecord[]
}

export function useSaveInsight() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (p: SaveInsightPayload) =>
      apiClient.post<Insight>('/insights', {
        dataset_id: p.datasetId,
        question: p.question,
        answer: p.answer,
        query: p.query,
        row_count: p.rowCount,
        findings: p.findings,
        title: p.title,
        tool_calls: p.toolCalls,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: INSIGHTS_KEY })
    },
  })
}

export function useRenameInsight() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      apiClient.patch<Insight>(`/insights/${id}`, { title }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: INSIGHTS_KEY }),
  })
}

/** Downloads an insight's standalone HTML report (prints cleanly to PDF). */
export async function downloadInsightReport(insight: Pick<Insight, 'id' | 'title'>) {
  const html = await apiClient.getText(`/insights/${insight.id}/report`)
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `pulseiq-report-${insight.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 60)}.html`
  link.click()
  URL.revokeObjectURL(url)
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
