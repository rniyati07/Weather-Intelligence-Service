import { Search, X } from 'lucide-react'
import { useId, type ComponentProps, type ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { Spinner } from '@/components/ui/spinner'

export interface SearchInputProps extends Omit<ComponentProps<'input'>, 'type' | 'id'> {
  label: string
  /** Hides the label visually. The search icon plus placeholder read as a search box. */
  hideLabel?: boolean
  loading?: boolean
  /** Shows a clear affordance when the field is non-empty (FDS §9.11). */
  onClear?: () => void
  /** Right-hand slot for a submit button, as on the landing hero. */
  trailing?: ReactNode
  id?: string
}

/**
 * Search field — the presentational shell only.
 *
 * Deliberately has no idea what it is searching. Debouncing, geocoding,
 * suggestion state and keyboard navigation of results belong to the search
 * feature; this component owns the input, the icon, the clear affordance and
 * the loading indicator, so it can be reused anywhere.
 *
 * `type="search"` is avoided: browsers add their own clear button, which would
 * sit alongside ours and behave differently.
 */
export function SearchInput({
  className,
  label,
  hideLabel = true,
  loading = false,
  onClear,
  trailing,
  value,
  id: providedId,
  ...props
}: SearchInputProps) {
  const generatedId = useId()
  const id = providedId ?? generatedId
  const hasValue = typeof value === 'string' && value.length > 0

  return (
    <div className="flex w-full flex-col gap-1.5">
      <label
        htmlFor={id}
        className={cn('text-body-sm font-medium text-muted-foreground', hideLabel && 'sr-only')}
      >
        {label}
      </label>

      <div
        className={cn(
          'flex h-14 w-full items-center gap-3 rounded-md border border-input bg-surface px-4',
          'transition-colors duration-150 ease-out',
          'focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/40',
          className,
        )}
      >
        <Search className="size-5 shrink-0 text-subtle-foreground" aria-hidden="true" />

        <input
          id={id}
          value={value}
          autoComplete="off"
          spellCheck={false}
          // `self-stretch` makes the input fill the box's height. Left at its
          // natural 24px, a tap in the padding above or below it would land on
          // the wrapper and focus nothing.
          className="min-w-0 flex-1 self-stretch bg-transparent text-body outline-none placeholder:text-subtle-foreground"
          {...props}
        />

        {loading ? <Spinner size="sm" label="Searching" /> : null}

        {hasValue && onClear ? (
          <button
            type="button"
            onClick={onClear}
            className="rounded-full p-1 text-subtle-foreground transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <X className="size-4" aria-hidden="true" />
            <span className="sr-only">Clear search</span>
          </button>
        ) : null}

        {trailing}
      </div>
    </div>
  )
}
