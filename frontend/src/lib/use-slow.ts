import { useEffect, useState } from 'react'

/** True once `pending` has lasted longer than `ms` — e.g. the free-tier
 * backend waking from sleep, which can take ~1 minute. */
export function useSlow(pending: boolean, ms = 4000) {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    if (!pending) return
    const id = window.setTimeout(() => setSlow(true), ms)
    return () => {
      window.clearTimeout(id)
      setSlow(false)
    }
  }, [pending, ms])
  return pending && slow
}
