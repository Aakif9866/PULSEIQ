import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--color-border)] px-6 py-4">
      <div>
        <h1 className="text-base font-semibold text-[var(--color-fg)]">{title}</h1>
        {description && <p className="mt-0.5 text-xs text-[var(--color-fg-muted)]">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
