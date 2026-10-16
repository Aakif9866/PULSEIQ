import type { AggregationOp, DatasetQueryRequest } from '@/types/dataset'

// Mirrors backend/app/schemas/analysis.py exactly — the hybrid AI
// Analyst's response shape (POST /datasets/{id}/analyze). Distinct from
// AskResponse (types/insight.ts), which is the older, single-query /ask
// path's shape.

export type AnomalyClassification =
  | 'statistical_outlier'
  | 'logical_violation'
  | 'missing_data'
  | 'duplicate'
  | 'referential_inconsistency'
  | 'cross_column_inconsistency'
  | 'temporal_anomaly'
  | 'potential_business_anomaly'
  | 'confirmed_data_quality_issue'
  | 'unknown'

export type ConfidenceLevel = 'high' | 'medium' | 'low'

export interface Finding {
  claim: string
  value: number | string | null
  unit: string | null
  affected_rows: number | null
  total_rows: number | null
  calculation: string | null
  classification: AnomalyClassification | null
  confidence: ConfidenceLevel
  evidence: string[]
  // Set by the backend's answer validator — false means this finding's
  // numbers couldn't be matched to anything in the actual tool-call
  // evidence. Never hidden when false; always shown, flagged.
  verified: boolean
}

export interface ToolCallRecord {
  tool: string
  arguments: Record<string, unknown>
  result: Record<string, unknown>
}

export interface ConversationTurn {
  question: string
  answer: string
}

export interface AnalyzeRequest {
  question: string
  conversation_history?: ConversationTurn[]
}

export interface AnalyzeResponse {
  question: string
  answer: string
  findings: Finding[]
  tool_calls: ToolCallRecord[]
  needs_clarification: string | null
  status: 'ok' | 'degraded'
  warnings: string[]
}

/** A tool_calls[].result carrying an "error" key is how app.ai.tool_specs
 * reports a tool failure — never an exception, always this shape. */
export function toolCallFailed(call: ToolCallRecord): string | null {
  const error = call.result?.error
  return typeof error === 'string' ? error : null
}

export interface ChartOption {
  label: string
  query: DatasetQueryRequest
}

/** Every chartable result in an answer: its successful group_by_aggregate
 * calls. That tool runs exactly this DatasetQueryRequest (backend
 * app/ai/tools.py), so a dashboard chart re-runs the same numbers live. No
 * other tool maps to one chartable query, so those get no chart rather than
 * a made-up one. The AI often computes several ("sum of revenue by region"
 * and "count of orders by region"), so the caller lets the user pick; this
 * only orders them: breakdowns before grand totals, then columns the
 * question mentions, then the latest call. Duplicates are dropped. */
export function chartOptionsFromToolCalls(calls: ToolCallRecord[], question = ''): ChartOption[] {
  const asked = question.toLowerCase()
  const seen = new Set<string>()
  const options: (ChartOption & { score: number; order: number })[] = []
  calls.forEach((call, order) => {
    if (call.tool !== 'group_by_aggregate' || toolCallFailed(call)) return
    const { group_by, column, op } = call.arguments as { group_by?: unknown; column?: unknown; op?: unknown }
    if (!Array.isArray(group_by) || typeof op !== 'string') return
    const groups = group_by.map(String)
    const col = typeof column === 'string' ? column : undefined
    const key = JSON.stringify([groups, col, op])
    if (seen.has(key)) return
    seen.add(key)
    const label = `${op} of ${col ?? 'rows'}${groups.length ? ` by ${groups.join(', ')}` : ' (total)'}`
    const score =
      (groups.length ? 2 : 0) + (col && asked.includes(col.toLowerCase().replaceAll('_', ' ')) ? 1 : 0)
    options.push({
      label,
      score,
      order,
      query: {
        group_by: groups,
        aggregations: [{ op: op as AggregationOp, column: col, alias: 'value' }],
        sort_by: 'value',
        sort_desc: true,
      },
    })
  })
  return options
    .sort((a, b) => b.score - a.score || b.order - a.order)
    .map(({ label, query }) => ({ label, query }))
}
