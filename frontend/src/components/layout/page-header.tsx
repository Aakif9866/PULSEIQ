import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] px-4 py-4 sm:px-6">
      <div>
        <h1 className="text-base font-semibold text-[var(--color-fg)]">{title}</h1>
        {description && <p className="mt-0.5 text-xs text-[var(--color-fg-muted)]">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
