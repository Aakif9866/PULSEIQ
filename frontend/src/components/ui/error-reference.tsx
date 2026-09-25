import { ApiError } from '@/lib/api-client'

/** The request id the server logged a failed request under, shown so a
 * user can quote it and it can be found in the backend's logs/traces
 * (docs/PHASES.md Phase 8 step 5). Renders nothing for non-API errors. */
export function ErrorReference({ error }: { error: unknown }) {
  if (!(error instanceof ApiError) || !error.requestId) return null
  return (
    <span className="mt-1 block text-[11px] text-[var(--color-fg-muted)]">
      Reference: <code className="select-all">{error.requestId}</code>
    </span>
  )
}
