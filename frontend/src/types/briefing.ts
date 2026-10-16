// Mirrors backend/app/schemas/briefing.py.

export interface TopContributor {
  dimension: string
  segment: string | number | boolean | null
  previous: number | null
  current: number | null
  change: number | null
  share_of_change_pct?: number | null
  flags?: string[]
}

export interface DatasetBriefing {
  overview: {
    rows: number
    columns: number
    data_quality_score: number | null
    duplicate_rows: number | null
    date_columns: string[]
    metric_columns: string[]
    dimension_columns: string[]
    id_columns: string[]
  }
  metrics: {
    column: string
    sum: number | null
    mean: number | null
    min: number | null
    max: number | null
    null_count: number
    additive: boolean
  }[]
  trend: {
    metric: string
    date_column: string
    freq: string
    series: { period: string; value: number | null }[]
    latest_change: {
      previous_period: string
      current_period: string
      previous_label: string
      current_label: string
      previous_value: number | null
      current_value: number | null
      change: number | null
      pct_change: number | null
      top_contributor: TopContributor | null
      caveats: string[]
    } | null
  } | null
  segments: {
    dimension: string
    metric: string
    op: 'sum'
    groups: { group: string | number | boolean | null; value: number | null }[]
    top_share_pct: number | null
    group_count: number
  } | null
  quality: {
    kind: 'missing' | 'outliers' | 'duplicates'
    column: string | null
    count: number
    pct?: number | null
  }[]
  relationships: {
    column_a: string
    column_b: string
    correlation: number
    direction: 'positive' | 'negative'
  }[]
  suggested_questions: string[]
}
