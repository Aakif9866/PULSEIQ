import type { Finding, ToolCallRecord } from '@/types/analysis'
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
  title: string
  question: string
  answer: string
  // Null for answers saved from AI Analysis (no single structured query).
  query_request: DatasetQueryRequest | null
  row_count: number | null
  findings: Finding[]
  tool_calls: ToolCallRecord[]
  /** Version it was computed on, vs the dataset's version now. */
  dataset_version: number | null
  current_dataset_version: number
  created_at: string
}
