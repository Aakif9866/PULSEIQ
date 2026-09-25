import { PageHeader } from '@/components/layout/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useMyUsage } from '@/features/usage/api'
import { ApiError } from '@/lib/api-client'
import type { UsageSummary } from '@/types/usage'

const numberFormat = new Intl.NumberFormat()

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-[var(--color-border)] px-4 py-3">
      <span className="text-xs text-[var(--color-fg-muted)]">{label}</span>
      <span className="text-lg font-semibold text-[var(--color-fg)]">{value}</span>
      {hint && <span className="text-xs text-[var(--color-fg-muted)]">{hint}</span>}
    </div>
  )
}

function QuotaBar({ usage }: { usage: UsageSummary }) {
  if (usage.quota_tokens === null) {
    return (
      <p className="text-sm text-[var(--color-fg-muted)]">
        No daily limit is configured on this server — usage is recorded but never blocked.
      </p>
    )
  }
  const pct = Math.min(100, (usage.total_tokens / usage.quota_tokens) * 100)
  const exhausted = usage.remaining_tokens === 0
  return (
    <div className="space-y-2">
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-[var(--color-border)]"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Daily token quota used"
      >
        <div
          className="h-full"
          style={{
            width: `${pct}%`,
            background: exhausted ? 'var(--color-negative)' : 'var(--color-accent)',
          }}
        />
      </div>
      <p className="text-sm text-[var(--color-fg)]">
        {numberFormat.format(usage.total_tokens)} of {numberFormat.format(usage.quota_tokens)}{' '}
        tokens used today
        {exhausted ? ' — limit reached.' : ` — ${numberFormat.format(usage.remaining_tokens ?? 0)} left.`}
      </p>
    </div>
  )
}

export function UsagePage() {
  const { data: usage, isLoading, error } = useMyUsage()

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Usage"
        description="Your AI Analysis usage today (UTC), measured from the model provider's own token counts."
      />
      <div className="flex flex-col gap-4 px-6 py-5">
        {isLoading && <p className="text-xs text-[var(--color-fg-muted)]">Loading usage…</p>}
        {error && (
          <p className="text-xs text-[var(--color-negative)]">
            {error instanceof ApiError ? error.message : "Couldn't load usage."}
          </p>
        )}

        {usage && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Daily limit</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <QuotaBar usage={usage} />
                <p className="text-xs text-[var(--color-fg-muted)]">
                  Resets {new Date(usage.resets_at).toLocaleString()}.
                </p>
              </CardContent>
            </Card>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Requests" value={numberFormat.format(usage.requests)} />
              <Stat
                label="Answered from cache"
                value={numberFormat.format(usage.cache_hits)}
                hint="No tokens spent"
              />
              <Stat
                label="Tokens"
                value={numberFormat.format(usage.total_tokens)}
                hint={`${numberFormat.format(usage.prompt_tokens)} in / ${numberFormat.format(usage.completion_tokens)} out`}
              />
              <Stat
                label="Estimated cost"
                value={
                  usage.estimated_cost_usd === null
                    ? 'Not tracked'
                    : `$${usage.estimated_cost_usd.toFixed(4)}`
                }
                hint={
                  usage.cost_tracking_configured
                    ? undefined
                    : 'Per-token pricing isn’t configured on this server'
                }
              />
            </div>

            <p className="text-xs text-[var(--color-fg-muted)]">
              Token counts cover AI Analysis. The older Ask and SQL paths are blocked once
              you're over the limit, but don't report their own token usage yet.
            </p>
          </>
        )}
      </div>
    </div>
  )
}
