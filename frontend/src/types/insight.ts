import type { ChartType } from '@/types/dashboard'
import type { DatasetQueryRequest, DatasetQueryResult } from '@/types/dataset'

export interface AskResponse {
  question: string
  answer: string
  query: DatasetQueryRequest
  result: DatasetQueryResult
  // Deterministic (backend rules, not AI-decided) — always a suggestion,
  // never applied without the user being able to change it.
  suggested_chart_type: ChartType
}

export interface Insight {
  id: string
  dataset_id: string
  dataset_filename: string
  question: string
  answer: string
  query_request: DatasetQueryRequest
  row_count: number
  created_at: string
}
