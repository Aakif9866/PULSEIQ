import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { useDeleteInsight, useInsights } from '@/features/insights/api'
import { formatDate } from '@/lib/utils'
import type { Insight } from '@/types/insight'
import { Star, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

export function InsightsPage() {
  const { data: insights, isLoading } = useInsights()
  const deleteInsight = useDeleteInsight()

  return (
    <div className="flex flex-col">
      <PageHeader title="Saved Insights" description="Insights you've saved from AI analyses." />

      <div className="px-6 py-5">
        {isLoading && <p className="text-xs text-[var(--color-fg-muted)]">Loading insights…</p>}

        {!isLoading && insights?.length === 0 && (
          <EmptyState
            icon={Star}
            title="No saved insights"
            description="Ask a question in the AI Analyst and save the answer to see it here."
            action={
              <Button size="sm" variant="secondary" asChild>
                <Link to="/workspace/ai-analyst">Go to AI Analyst</Link>
              </Button>
            }
          />
        )}

        {insights && insights.length > 0 && (
          <div className="flex flex-col gap-3">
            {insights.map((insight) => (
              <InsightCard
                key={insight.id}
                insight={insight}
                onDelete={() => deleteInsight.mutate(insight.id)}
                deleting={deleteInsight.isPending && deleteInsight.variables === insight.id}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function InsightCard({
  insight,
  onDelete,
  deleting,
}: {
  insight: Insight
  onDelete: () => void
  deleting: boolean
}) {
  return (
    <Card>
      <CardContent className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-[var(--color-fg)]">{insight.question}</p>
            <p className="text-xs text-[var(--color-fg-muted)]">
              {insight.dataset_filename} · {formatDate(insight.created_at)}
            </p>
          </div>
          <Button size="icon" variant="ghost" onClick={onDelete} disabled={deleting}>
            <Trash2 className="h-4 w-4" strokeWidth={1.75} />
          </Button>
        </div>
        <p className="text-sm text-[var(--color-fg-muted)]">{insight.answer}</p>
      </CardContent>
    </Card>
  )
}
