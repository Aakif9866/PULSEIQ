import { cn } from '@/lib/utils'
import { forwardRef } from 'react'

export const Label = forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn('text-xs font-medium text-[var(--color-fg-muted)]', className)}
      {...props}
    />
  ),
)
Label.displayName = 'Label'
