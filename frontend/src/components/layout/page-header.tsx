import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 px-4 pb-1 pt-6 sm:px-6 sm:pt-8">
      <div>
        <h1 className="text-2xl font-bold leading-tight text-[var(--color-fg)] sm:text-[1.75rem]">{title}</h1>
        {description && <p className="mt-1 text-sm text-[var(--color-fg-muted)]">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
