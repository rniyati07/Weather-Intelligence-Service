import { Skeleton, SkeletonText } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export interface LoadingSkeletonProps {
  /**
   * Which real content this stands in for. Shape-matching is the whole point:
   * a skeleton that matches the layout it replaces means nothing jumps when the
   * data lands (FDS §6.6).
   */
  variant?: 'text' | 'card' | 'metric' | 'list' | 'table'
  /** Rows, lines or cards, depending on the variant. */
  count?: number
  className?: string
  /** Announced to assistive tech while the region is busy. */
  label?: string
}

/**
 * Region-level loading placeholder.
 *
 * Never a spinner for a card region — see `Spinner` for why. The region carries
 * `aria-busy` and a polite status label; the skeleton bones themselves are
 * `aria-hidden`, so a screen reader hears "Loading trip verdict", not a
 * description of grey rectangles.
 */
export function LoadingSkeleton({
  variant = 'text',
  count = 3,
  className,
  label = 'Loading',
}: LoadingSkeletonProps) {
  return (
    <div aria-busy="true" aria-live="polite" className={className}>
      <span className="sr-only">{label}</span>
      {renderVariant(variant, count)}
    </div>
  )
}

function renderVariant(variant: NonNullable<LoadingSkeletonProps['variant']>, count: number) {
  switch (variant) {
    case 'text':
      return <SkeletonText lines={count} />

    case 'metric':
      return (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-11 w-32" />
        </div>
      )

    case 'card':
      return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: count }, (_, index) => (
            <div
              key={index}
              className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-6"
            >
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-3 w-full" />
            </div>
          ))}
        </div>
      )

    case 'list':
      return (
        <div className="flex flex-col gap-3">
          {Array.from({ length: count }, (_, index) => (
            <div key={index} className="flex items-center gap-3">
              <Skeleton className="size-9 rounded-full" />
              <div className="flex flex-1 flex-col gap-1.5">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          ))}
        </div>
      )

    case 'table':
      return (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-9 w-full" />
          {Array.from({ length: count }, (_, index) => (
            <Skeleton key={index} className={cn('h-11 w-full', index % 2 === 1 && 'opacity-70')} />
          ))}
        </div>
      )
  }
}
