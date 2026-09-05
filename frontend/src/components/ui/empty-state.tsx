import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-[var(--color-border-strong)] px-6 py-12 text-center',
        className,
      )}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[var(--color-surface-raised)]">
        <Icon className="h-5 w-5 text-[var(--color-fg-muted)]" strokeWidth={1.5} />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-[var(--color-fg)]">{title}</p>
        <p className="max-w-sm text-xs text-[var(--color-fg-muted)]">{description}</p>
      </div>
      {action}
    </div>
  )
}
