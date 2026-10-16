import { cn } from '@/lib/utils'
import { forwardRef } from 'react'

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(
          'flex h-9 w-full rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-3 text-sm text-[var(--color-fg)] outline-none transition-[border-color,box-shadow] duration-150 focus-visible:border-[var(--color-accent)] focus-visible:ring-4 focus-visible:ring-[var(--color-focus)] disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      />
    )
  },
)
Select.displayName = 'Select'
