import { AiAnalystPage } from '@/pages/ai-analyst-page'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/components/ai/analyze-analyst-view', () => ({
  AnalyzeAnalystView: () => <div>analyze-view</div>,
}))
vi.mock('@/components/ai/ask-analyst-view', () => ({
  AskAnalystView: () => <div>ask-view</div>,
}))

const flags = vi.hoisted(() => ({ engine: 'analyze' as 'analyze' | 'ask' }))
vi.mock('@/lib/feature-flags', () => ({
  getAiAnalystEngine: () => flags.engine,
}))

describe('AiAnalystPage', () => {
  it('renders the hybrid /analyze view by default', () => {
    flags.engine = 'analyze'
    render(<AiAnalystPage />)
    expect(screen.getByText('analyze-view')).toBeInTheDocument()
    expect(screen.queryByText('ask-view')).not.toBeInTheDocument()
  })

  it('renders the deprecated /ask view when the flag is set to "ask"', () => {
    flags.engine = 'ask'
    render(<AiAnalystPage />)
    expect(screen.getByText('ask-view')).toBeInTheDocument()
    expect(screen.queryByText('analyze-view')).not.toBeInTheDocument()
  })
})
