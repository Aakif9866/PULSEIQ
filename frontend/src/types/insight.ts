import type { DatasetQueryRequest, DatasetQueryResult } from '@/types/dataset'

export interface AskResponse {
  question: string
  answer: string
  query: DatasetQueryRequest
  result: DatasetQueryResult
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
