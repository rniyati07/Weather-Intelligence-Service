import { usePreferences } from '@/hooks/usePreferences'
import { cn } from '@/lib/utils'
import type { TemperatureUnit } from '@/types'

const OPTIONS: { unit: TemperatureUnit; label: string; full: string }[] = [
  { unit: 'celsius', label: '°C', full: 'Celsius' },
  { unit: 'fahrenheit', label: '°F', full: 'Fahrenheit' },
]

/**
 * Temperature unit switch.
 *
 * A radiogroup rather than a single toggle button: both states are visible, so
 * a user can see which unit is active without inferring it from a label that
 * might describe either the current state or the action.
 *
 * Applies instantly with no refetch — the API is metric and fixed in v1, so
 * Fahrenheit is a client-side conversion (API Spec §5).
 *
 * Shared because it appears in the dashboard header and again in Settings.
 */
export function UnitsToggle({ className }: { className?: string }) {
  const { temperatureUnit, setTemperatureUnit } = usePreferences()

  return (
    <div
      role="radiogroup"
      aria-label="Temperature unit"
      className={cn('inline-flex items-center rounded-full bg-muted p-0.5', className)}
    >
      {OPTIONS.map((option) => {
        const active = option.unit === temperatureUnit

        return (
          <button
            key={option.unit}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => {
              setTemperatureUnit(option.unit)
            }}
            className={cn(
              'inline-flex h-11 min-w-11 items-center justify-center rounded-full px-3',
              'text-body-sm font-medium transition-colors duration-150 ease-out',
              'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
              active
                ? 'bg-primary-subtle text-primary'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <span aria-hidden="true">{option.label}</span>
            <span className="sr-only">{option.full}</span>
          </button>
        )
      })}
    </div>
  )
}
