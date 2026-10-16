import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

/** An icon on a soft tint of its own color — the app's main pop of color.
 * `color` is a CSS color, normally a token like 'var(--color-purple)'. */
export function IconChip({
  icon: Icon,
  color = 'var(--color-accent)',
  className,
}: {
  icon: LucideIcon
  color?: string
  className?: string
}) {
  return (
    <span
      className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg', className)}
      style={{ color, backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)` }}
    >
      <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
    </span>
  )
}
