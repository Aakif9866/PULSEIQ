import type { DatasetQueryRequest } from '@/types/dataset'

export type ChartType = 'bar' | 'line'

export interface Dashboard {
  id: string
  name: string
  chart_count: number
  created_at: string
}

export interface DashboardChart {
  id: string
  dataset_id: string
  dataset_filename: string
  title: string
  chart_type: ChartType
  query_request: DatasetQueryRequest
  position: number
  created_at: string
}

export interface DashboardDetail {
  id: string
  name: string
  created_at: string
  charts: DashboardChart[]
}
