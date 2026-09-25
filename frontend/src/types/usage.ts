// Mirrors backend/app/schemas/usage.py — GET /usage/me.
export interface UsageSummary {
  day_start: string
  resets_at: string
  requests: number
  cache_hits: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  // null = pricing isn't configured on the server, i.e. "unknown" — never
  // shown as $0.00.
  estimated_cost_usd: number | null
  // null = no daily quota configured.
  quota_tokens: number | null
  remaining_tokens: number | null
  cost_tracking_configured: boolean
}
