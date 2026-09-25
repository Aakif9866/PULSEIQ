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
