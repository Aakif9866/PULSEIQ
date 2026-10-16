import { usePublicStats } from '@/features/datasets/api'
import { Users } from 'lucide-react'

/** "N users signed up" — public, so it shows before and after login. */
export function UserCount() {
  const { data: stats } = usePublicStats()
  if (!stats) return null
  const n = stats.total_users
  return (
    <span
      className="flex items-center gap-1.5 whitespace-nowrap rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs tabular-nums text-[var(--color-fg-muted)]"
      title={`${n.toLocaleString()} ${n === 1 ? 'user has' : 'users have'} signed up`}
    >
      <span
        aria-hidden="true"
        className="h-2 w-2 rounded-full bg-[var(--color-positive)] shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-positive)_25%,transparent)]"
      />
      <Users className="h-3.5 w-3.5 text-[var(--color-accent)]" strokeWidth={1.75} />
      {n.toLocaleString()}
      <span className="hidden sm:inline">{n === 1 ? 'user' : 'users'} signed up</span>
    </span>
  )
}
