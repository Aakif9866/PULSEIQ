import { getAiAnalystEngine } from '@/lib/feature-flags'
import { afterEach, describe, expect, it, vi } from 'vitest'

describe('getAiAnalystEngine', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('defaults to the hybrid /analyze engine when unset', () => {
    vi.stubEnv('VITE_AI_ANALYST_ENGINE', '')
    expect(getAiAnalystEngine()).toBe('analyze')
  })

  it('falls back to /analyze on an invalid value instead of throwing', () => {
    vi.stubEnv('VITE_AI_ANALYST_ENGINE', 'nonsense')
    expect(getAiAnalystEngine()).toBe('analyze')
  })

  it('honors an explicit "ask" to keep the deprecated path reachable', () => {
    vi.stubEnv('VITE_AI_ANALYST_ENGINE', 'ask')
    expect(getAiAnalystEngine()).toBe('ask')
  })
})
