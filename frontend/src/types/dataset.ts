export interface TopValue {
  value: unknown
  count: number
}

export interface ColumnProfile {
  name: string
  dtype: string
  null_count: number
  null_percentage: number
  min: number | null
  max: number | null
  mean: number | null
  outlier_count: number | null
  top_values: TopValue[] | null
}

export interface Correlation {
  column_a: string
  column_b: string
  correlation: number
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
  duplicate_row_count: number | null
  data_quality_score: number | null
  correlations: Correlation[] | null
  /** Current version (1 until a new file is uploaded over it). */
  version: number
}

export interface SchemaChanges {
  previous_version: number
  added: string[]
  removed: string[]
  type_changed: { column: string; from: string; to: string }[]
  row_count_change: number | null
}

export interface DatasetVersion {
  version: number
  original_filename: string
  size_bytes: number
  row_count: number | null
  column_count: number | null
  schema_changes: SchemaChanges | null
  /** False once an old version's file has been pruned (history row kept). */
  file_kept: boolean
  created_at: string
}

export interface VersionUploadResult {
  dataset: Dataset
  version: DatasetVersion
  checks_run: number
  new_anomalies: number
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
