import { PageHeader } from '@/components/layout/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import type { LucideIcon } from 'lucide-react'

interface PlaceholderPageProps {
  title: string
  description: string
  icon: LucideIcon
  emptyTitle: string
  emptyDescription: string
}

/**
 * Shared shell for workspace sections not yet built out (datasets,
 * dashboards, AI analyst, insights, settings land in later phases).
 */
export function PlaceholderPage({
  title,
  description,
  icon,
  emptyTitle,
  emptyDescription,
}: PlaceholderPageProps) {
  return (
    <div className="flex flex-col">
      <PageHeader title={title} description={description} />
      <div className="px-6 py-5">
        <EmptyState icon={icon} title={emptyTitle} description={emptyDescription} />
      </div>
    </div>
  )
}
