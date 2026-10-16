import { cn } from '@/lib/utils'
import { Slot } from '@radix-ui/react-slot'
import { type VariantProps, cva } from 'class-variance-authority'
import { forwardRef } from 'react'

const buttonVariants = cva(
  'inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-[background-color,color,filter,transform] duration-100 ease-out active:scale-[0.97] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--color-focus)] disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default:
          'bg-[linear-gradient(180deg,color-mix(in_srgb,var(--color-accent)_80%,white),var(--color-accent))] text-[var(--color-accent-fg)] shadow-[0_1px_2px_rgb(0_0_0/0.12),0_4px_14px_-4px_color-mix(in_srgb,var(--color-accent)_60%,transparent)] hover:brightness-110 active:brightness-95',
        secondary:
          'bg-[var(--color-surface)] text-[var(--color-fg)] border border-[var(--color-border-strong)] shadow-[var(--shadow-card)] hover:bg-[var(--color-surface-raised)]',
        ghost: 'text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-fg)]',
        destructive: 'bg-[var(--color-negative)] text-white hover:brightness-110',
      },
      size: {
        default: 'h-9 px-4',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-10 px-6',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
    )
  },
)
Button.displayName = 'Button'
