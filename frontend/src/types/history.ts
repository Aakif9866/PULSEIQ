import type { DatasetQueryResult } from '@/types/dataset'

// Mirrors backend/app/schemas/history.py and AskSqlResponse in schemas/ai.py.

export type QuerySource = 'ai_sql' | 'sql_explorer' | 'ai_structured' | 'ai_deep_analysis'

export interface RunSqlResponse {
  sql: string
  result: DatasetQueryResult
}

export interface AskSqlResponse {
  question: string
  answer: string
  generated_sql: string
  result: DatasetQueryResult
}

export interface QueryHistoryItem {
  id: string
  dataset_id: string
  question: string | null
  sql_text: string | null
  source: QuerySource
  row_count: number
  columns: string[]
  truncated: boolean
  created_at: string
}

export interface SavedQuery {
  id: string
  dataset_id: string
  name: string
  sql_text: string
  created_at: string
}

export interface SuggestedQuery {
  label: string
  sql: string
}
