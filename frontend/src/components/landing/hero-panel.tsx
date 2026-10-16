/**
 * Decorative, static preview of the AI Analyst workspace shown in the
 * landing page hero. Not wired to real data — purely illustrative.
 */
const SPARKLINE_POINTS = [12, 18, 15, 24, 21, 30, 27, 38, 34, 44, 40, 52]

function buildPath(values: number[], width: number, height: number) {
  const max = Math.max(...values)
  const min = Math.min(...values)
  const stepX = width / (values.length - 1)
  return values
    .map((v, i) => {
      const x = i * stepX
      const y = height - ((v - min) / (max - min)) * height
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

export function HeroPanel() {
  const path = buildPath(SPARKLINE_POINTS, 280, 64)

  return (
    <div className="relative w-full max-w-md overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl shadow-black/40">
      <div className="flex items-center gap-1.5 border-b border-[var(--color-border)] px-4 py-2.5">
        <span className="h-2 w-2 rounded-full bg-[var(--color-negative)]/60" />
        <span className="h-2 w-2 rounded-full bg-[var(--color-warning)]/60" />
        <span className="h-2 w-2 rounded-full bg-[var(--color-positive)]/60" />
        <span className="ml-2 text-[11px] text-[var(--color-fg-subtle)]">
          revenue_by_region.csv — AI Analyst
        </span>
      </div>

      <div className="space-y-3 p-4">
        <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-[linear-gradient(135deg,var(--color-accent),var(--color-indigo))] px-3.5 py-2 text-xs text-white shadow-[0_4px_14px_-6px_var(--color-indigo)]">
          Show the monthly revenue trend and explain the biggest decline.
        </div>

        <div className="rounded-md border border-[var(--color-border)] p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-medium text-[var(--color-fg-muted)]">
              Monthly revenue
            </span>
            <span className="text-[11px] text-[var(--color-negative)]">−12.4% in March</span>
          </div>
          <svg viewBox="0 0 280 64" className="h-16 w-full" aria-hidden="true">
            <defs>
              <linearGradient id="hero-line" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0%" stopColor="var(--color-accent)" />
                <stop offset="100%" stopColor="var(--color-purple)" />
              </linearGradient>
              <linearGradient id="hero-fill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--color-purple)" stopOpacity="0.25" />
                <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path d={`${path} L280,64 L0,64 Z`} fill="url(#hero-fill)" />
            <path d={path} fill="none" stroke="url(#hero-line)" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'Total revenue', value: '$2.4M', color: 'var(--color-fg)' },
            { label: 'YoY growth', value: '+18%', color: 'var(--color-positive)' },
            { label: 'Top segment', value: 'Enterprise', color: 'var(--color-purple)' },
          ].map((kpi) => (
            <div key={kpi.label} className="rounded-md border border-[var(--color-border)] px-2.5 py-2">
              <p className="text-[10px] uppercase tracking-wide text-[var(--color-fg-subtle)]">
                {kpi.label}
              </p>
              <p className="mt-0.5 text-sm font-semibold tabular-nums" style={{ color: kpi.color }}>
                {kpi.value}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
