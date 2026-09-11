import type { AggregationOp } from '@/types/dataset'

export type BaselineStrategy = 'previous_period' | 'moving_average' | 'zscore'
export type CheckFrequency = 'hourly' | 'daily' | 'manual'
export type MonitorStatus = 'NO_ANOMALY' | 'ANOMALY_DETECTED' | 'INSUFFICIENT_DATA' | 'ERROR'
export type Direction = 'increase' | 'decrease'
export type Severity = 'low' | 'medium' | 'high'

export interface Monitor {
  id: string
  dataset_id: string
  dataset_filename: string
  name: string
  metric_column: string
  aggregation: AggregationOp
  time_column: string
  baseline_strategy: BaselineStrategy
  baseline_window: number
  threshold_percent: number | null
  zscore_threshold: number | null
  check_frequency: CheckFrequency
  notify_email: boolean
  is_enabled: boolean
  last_checked_at: string | null
  last_status: MonitorStatus | null
  last_error: string | null
  created_at: string
}

export interface MonitorCreate {
  dataset_id: string
  name: string
  metric_column: string
  aggregation: AggregationOp
  time_column: string
  baseline_strategy: BaselineStrategy
  baseline_window?: number
  threshold_percent?: number | null
  zscore_threshold?: number | null
  check_frequency: CheckFrequency
  notify_email: boolean
}

export interface MonitorUpdate {
  name?: string
  baseline_strategy?: BaselineStrategy
  baseline_window?: number
  threshold_percent?: number | null
  zscore_threshold?: number | null
  check_frequency?: CheckFrequency
  notify_email?: boolean
  is_enabled?: boolean
}

export interface Anomaly {
  id: string
  monitor_id: string
  monitor_name: string
  dataset_id: string
  metric_column: string
  period_label: string
  observed_value: number
  baseline_value: number | null
  change_percent: number | null
  direction: Direction
  detection_method: string
  severity: Severity
  explanation: string | null
  alert_sent: boolean
  alert_sent_at: string | null
  alert_error: string | null
  created_at: string
}

export interface MonitorRunResult {
  status: MonitorStatus
  message: string | null
  anomaly: Anomaly | null
}
