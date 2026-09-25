import { AnalyzeAnalystView } from '@/components/ai/analyze-analyst-view'
import { AskAnalystView } from '@/components/ai/ask-analyst-view'
import { PageHeader } from '@/components/layout/page-header'
import { getAiAnalystEngine } from '@/lib/feature-flags'

export function AiAnalystPage() {
  const engine = getAiAnalystEngine()

  return (
    <div className="flex flex-col">
      <PageHeader
        title="AI Analysis"
        description="Ask questions about your data in plain language."
      />
      {engine === 'ask' ? <AskAnalystView /> : <AnalyzeAnalystView />}
    </div>
  )
}
