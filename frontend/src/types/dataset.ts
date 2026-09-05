export interface ColumnProfile {
  name: string
  dtype: string
  null_count: number
}

export interface Dataset {
  id: string
  original_filename: string
  content_type: string
  size_bytes: number
  status: string
  created_at: string
  row_count: number | null
  column_count: number | null
  columns_profile: ColumnProfile[] | null
}

export type AggregationOp = 'sum' | 'avg' | 'min' | 'max' | 'count'
export type FilterOp = 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains'

export interface Aggregation {
  op: AggregationOp
  column?: string
  alias?: string
}

export interface QueryFilter {
  column: string
  op: FilterOp
  value: string | number | boolean
}

export interface DatasetQueryRequest {
  group_by?: string[]
  aggregations?: Aggregation[]
  filters?: QueryFilter[]
  sort_by?: string
  sort_desc?: boolean
  limit?: number
}

export interface DatasetQueryResult {
  columns: string[]
  rows: unknown[][]
  row_count: number
  truncated: boolean
}
