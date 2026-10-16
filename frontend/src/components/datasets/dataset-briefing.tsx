import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { IconChip } from '@/components/ui/icon-chip'
import { useDatasetBriefing } from '@/features/datasets/api'
import { buildChartOption } from '@/lib/chart-options'
import { useTheme } from '@/lib/theme'
import type { DatasetBriefing as Briefing } from '@/types/briefing'
import ReactECharts from 'echarts-for-react'
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  GitCompareArrows,
  Lightbulb,
  Sparkles,
  TrendingUp,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const fmt = (n: number | null | undefined) =>
  n === null || n === undefined
    ? '—'
    : Math.abs(n) >= 1000
      ? n.toLocaleString(undefined, { maximumFractionDigits: 0 })
      : n.toLocaleString(undefined, { maximumFractionDigits: 2 })

/** The dataset's briefing: every number computed server-side from the
 * full data (backend app/analytics/briefing.py); sections that don't apply
 * to this dataset are simply absent. */
export function DatasetBriefing({ datasetId }: { datasetId: string }) {
  const { data, isLoading, isError } = useDatasetBriefing(datasetId)

  if (isLoading) {
    return (
      <Card aria-busy="true">
        <CardContent className="space-y-3 py-5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-4 animate-pulse rounded bg-[var(--color-surface-raised)]" style={{ width: `${90 - i * 20}%` }} />
          ))}
        </CardContent>
      </Card>
    )
  }
  if (isError || !data) {
    return (
      <Card>
        <CardContent className="py-4 text-sm text-[var(--color-fg-muted)]">
          The briefing couldn&apos;t be built for this dataset. The column profile and explorer below
          still work.
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-3">
        <IconChip icon={Lightbulb} color="var(--color-orange)" />
        <div>
          <CardTitle>Briefing</CardTitle>
          <p className="text-xs text-[var(--color-fg-muted)]">
            Computed from all {fmt(data.overview.rows)} rows. No AI involved, so every number is exact.
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 py-4">
        <Metrics briefing={data} />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {data.trend && <Trend trend={data.trend} />}
          {data.segments && <Segments segments={data.segments} />}
        </div>
        <Notes briefing={data} />
        <SuggestedQuestions datasetId={datasetId} questions={data.suggested_questions} />
      </CardContent>
    </Card>
  )
}

function Metrics({ briefing }: { briefing: Briefing }) {
  if (briefing.metrics.length === 0) return null
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {briefing.metrics.map((m) => (
        <div key={m.column} className="rounded-lg border border-[var(--color-border)] px-3 py-2.5">
          {/* Totals of prices, ages or rates mean nothing: show those by average. */}
          <p className="truncate text-xs text-[var(--color-fg-muted)]">
            {m.additive ? 'Total' : 'Average'} {m.column}
          </p>
          <p className="text-xl font-semibold tabular-nums">{fmt(m.additive ? m.sum : m.mean)}</p>
          <p className="text-xs text-[var(--color-fg-subtle)] tabular-nums">
            {m.additive ? `avg ${fmt(m.mean)} · ` : ''}range {fmt(m.min)} – {fmt(m.max)}
          </p>
        </div>
      ))}
    </div>
  )
}

function Trend({ trend }: { trend: NonNullable<Briefing['trend']> }) {
  const theme = useTheme()
  const lc = trend.latest_change
  const up = (lc?.change ?? 0) >= 0
  return (
    <section aria-label="Trend" className="rounded-lg border border-[var(--color-border)] p-3">
      <p className="mb-1 flex items-center gap-1.5 text-sm font-medium">
        <TrendingUp className="h-4 w-4 text-[var(--color-accent)]" strokeWidth={1.75} />
        {trend.metric} by {trend.freq}
      </p>
      <ReactECharts
        option={buildChartOption(
          {
            columns: [trend.date_column, trend.metric],
            rows: trend.series.map((p) => [p.period.slice(0, 10), p.value]),
            row_count: trend.series.length,
            truncated: false,
          },
          'line',
          theme,
        )}
        style={{ height: 180 }}
        opts={{ renderer: 'svg' }}
      />
      {lc && (
        <p className="mt-1 text-sm text-[var(--color-fg-muted)]">
          <span className="font-medium text-[var(--color-fg)]">{lc.current_label}</span> vs{' '}
          {lc.previous_label}:{' '}
          <span
            className="inline-flex items-center font-medium tabular-nums"
            style={{ color: up ? 'var(--color-positive)' : 'var(--color-negative)' }}
          >
            {up ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
            {fmt(lc.change)}
            {lc.pct_change !== null && ` (${lc.pct_change > 0 ? '+' : ''}${lc.pct_change}%)`}
          </span>
          {lc.top_contributor && (
            <>
              . Biggest contributor: {lc.top_contributor.dimension}{' '}
              <span className="font-medium text-[var(--color-fg)]">{String(lc.top_contributor.segment)}</span> (
              {fmt(lc.top_contributor.change)})
            </>
          )}
          .
        </p>
      )}
      {lc?.caveats.map((c) => (
        <p key={c} className="mt-1 flex gap-1.5 text-xs text-[var(--color-warning)]">
          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" strokeWidth={2} />
          {c}
        </p>
      ))}
    </section>
  )
}

function Segments({ segments }: { segments: NonNullable<Briefing['segments']> }) {
  const theme = useTheme()
  return (
    <section aria-label="Segments" className="rounded-lg border border-[var(--color-border)] p-3">
      <p className="mb-1 flex items-center gap-1.5 text-sm font-medium">
        <GitCompareArrows className="h-4 w-4 text-[var(--color-indigo)]" strokeWidth={1.75} />
        Total {segments.metric} by {segments.dimension}
      </p>
      <ReactECharts
        option={buildChartOption(
          {
            columns: [segments.dimension, segments.metric],
            rows: segments.groups.map((g) => [String(g.group), g.value]),
            row_count: segments.groups.length,
            truncated: false,
          },
          'bar',
          theme,
        )}
        style={{ height: 180 }}
        opts={{ renderer: 'svg' }}
      />
      {segments.top_share_pct !== null && (
        <p className="mt-1 text-sm text-[var(--color-fg-muted)]">
          <span className="font-medium text-[var(--color-fg)]">{String(segments.groups[0]?.group)}</span>{' '}
          accounts for {segments.top_share_pct}% of the total
          {segments.group_count > segments.groups.length && ` (top ${segments.groups.length} of ${segments.group_count} shown)`}.
        </p>
      )}
    </section>
  )
}

function Notes({ briefing }: { briefing: Briefing }) {
  const quality = briefing.quality.slice(0, 4)
  if (quality.length === 0 && briefing.relationships.length === 0) return null
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {quality.length > 0 && (
        <section aria-label="Data quality">
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--color-fg-subtle)]">
            Data quality
          </p>
          <ul className="space-y-1 text-sm text-[var(--color-fg-muted)]">
            {quality.map((q) => (
              <li key={`${q.kind}-${q.column}`}>
                {q.kind === 'duplicates'
                  ? `${q.count} duplicate ${q.count === 1 ? 'row' : 'rows'}`
                  : q.kind === 'missing'
                    ? `${q.count} missing ${q.count === 1 ? 'value' : 'values'} in ${q.column}${q.pct ? ` (${q.pct}%)` : ''}`
                    : `${q.count} ${q.count === 1 ? 'outlier' : 'outliers'} in ${q.column}`}
              </li>
            ))}
          </ul>
        </section>
      )}
      {briefing.relationships.length > 0 && (
        <section aria-label="Relationships">
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--color-fg-subtle)]">
            Strong relationships
          </p>
          <ul className="space-y-1 text-sm text-[var(--color-fg-muted)]">
            {briefing.relationships.map((r) => (
              <li key={`${r.column_a}-${r.column_b}`}>
                {r.column_a} and {r.column_b}: {r.direction} (r = {r.correlation})
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function SuggestedQuestions({ datasetId, questions }: { datasetId: string; questions: string[] }) {
  return (
    <section aria-label="Suggested questions">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--color-fg-subtle)]">
        Ask the AI analyst
      </p>
      <div className="flex flex-wrap gap-2">
        {questions.map((q) => (
          <Link
            key={q}
            to={`/workspace/ai-analyst?dataset=${datasetId}&q=${encodeURIComponent(q)}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border-strong)] px-3 py-1.5 text-xs text-[var(--color-fg)] transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] active:scale-[0.98]"
          >
            <Sparkles className="h-3 w-3 text-[var(--color-purple)]" strokeWidth={2} />
            {q}
          </Link>
        ))}
      </div>
    </section>
  )
}
