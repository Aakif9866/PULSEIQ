import { IconChip } from '@/components/ui/icon-chip'
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

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-[var(--color-border-strong)] px-6 py-12 text-center',
        className,
      )}
    >
      <IconChip icon={icon} className="h-11 w-11 rounded-xl" />
      <div className="space-y-1">
        <p className="text-sm font-medium text-[var(--color-fg)]">{title}</p>
        <p className="max-w-sm text-xs text-[var(--color-fg-muted)]">{description}</p>
      </div>
      {action}
    </div>
  )
}
