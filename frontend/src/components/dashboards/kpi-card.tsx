import type { DatasetQueryResult } from '@/types/dataset'

/** Auto-compact formatting for a hero number (dataviz skill's stat-tile
 * contract: "1,284 / 12.9K / $4.2M") — proportional figures, not
 * tabular-nums (that's reserved for columns of aligned numbers). */
function formatHeroNumber(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return String(value ?? '—')
  const abs = Math.abs(value)
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return value.toLocaleString()
}

interface KpiCardProps {
  label: string
  result: DatasetQueryResult
}

/** A single headline number — the dataviz skill's "hero figure," not a
 * chart at all, which is exactly why kpi/table chart types never reach
 * buildChartOption(). Only ever shows the first row's first column;
 * anything more belongs on a real chart instead. */
export function KpiCard({ label, result }: KpiCardProps) {
  const value = result.rows[0]?.[0]

  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
      <p className="text-xs font-medium text-[var(--color-fg-muted)]">{label}</p>
      <p className="font-sans text-5xl font-semibold text-[var(--color-fg)]">
        {formatHeroNumber(value)}
      </p>
    </div>
  )
}
