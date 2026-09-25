// PulseIQ V2 Phase 8, Step 1 (docs/PHASES.md): the AI Analysis page moved
// from the old, unvalidated /ask endpoint to the hybrid, tool-grounded
// /analyze engine. /ask is kept reachable behind this flag rather than
// deleted outright — see docs/AI_ANALYTICS.md's "Deprecated: /ask" note.
export type AiAnalystEngine = 'analyze' | 'ask'

const VALID_ENGINES: AiAnalystEngine[] = ['analyze', 'ask']

export function getAiAnalystEngine(): AiAnalystEngine {
  const raw = import.meta.env.VITE_AI_ANALYST_ENGINE
  return VALID_ENGINES.includes(raw as AiAnalystEngine) ? (raw as AiAnalystEngine) : 'analyze'
}
