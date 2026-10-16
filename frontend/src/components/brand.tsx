import { cn } from '@/lib/utils'
import { Activity } from 'lucide-react'

/** The PulseIQ mark + wordmark, shared by every page header. */
export function Brand({ size = 'md' }: { size?: 'sm' | 'md' }) {
  const small = size === 'sm'
  return (
    <span className="flex items-center gap-2">
      <span
        className={cn(
          'flex items-center justify-center bg-[linear-gradient(135deg,var(--color-accent),var(--color-indigo))] shadow-[0_2px_8px_-2px_color-mix(in_srgb,var(--color-indigo)_60%,transparent)]',
          small ? 'h-6 w-6 rounded-[7px]' : 'h-7 w-7 rounded-[8px]',
        )}
      >
        <Activity
          className={cn('text-[var(--color-accent-fg)]', small ? 'h-3.5 w-3.5' : 'h-4 w-4')}
          strokeWidth={2.5}
        />
      </span>
      <span className={cn('font-semibold tracking-tight', small ? 'text-sm' : 'text-base')}>
        PulseIQ
      </span>
    </span>
  )
}
