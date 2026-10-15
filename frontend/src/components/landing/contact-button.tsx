import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Mail } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

const EMAIL = 'aakif9866@gmail.com'

/** Shows the contact email in a small box next to the button — no mailto. */
export function ContactButton({ side = 'bottom' }: { side?: 'top' | 'bottom' }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node))
        setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(EMAIL)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard blocked: the address is still visible and selectable.
    }
  }

  return (
    <div ref={ref} className="relative inline-block">
      <Button variant="ghost" size="sm" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Mail className="h-4 w-4" strokeWidth={1.75} />
        Contact me
      </Button>
      {open && (
        <div
          role="dialog"
          aria-label="Contact email"
          className={cn(
            'absolute right-0 z-20 flex items-center gap-2 whitespace-nowrap rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm shadow-lg',
            side === 'top' ? 'bottom-full mb-2' : 'top-full mt-2',
          )}
        >
          <span className="select-all text-[var(--color-fg)]">{EMAIL}</span>
          <Button variant="secondary" size="sm" onClick={copy}>
            {copied ? 'Copied' : 'Copy'}
          </Button>
        </div>
      )}
    </div>
  )
}
