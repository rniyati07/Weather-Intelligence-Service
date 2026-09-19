import { cn } from '@/lib/utils'

export interface SwitchProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  /** Accessible name. Required — the visual label lives in the row beside it. */
  label: string
  describedBy?: string
}

/**
 * An on/off preference.
 *
 * A native `<button role="switch">` rather than a styled checkbox: `switch`
 * announces "on"/"off", which is what this control means, where a checkbox
 * announces "checked" — subtly wrong for a setting that takes effect
 * immediately rather than being submitted.
 *
 * Feature-local by the project's extraction rule: exactly one consumer today.
 * Promote to `components/ui` when a second appears.
 */
export function Switch({ checked, onCheckedChange, label, describedBy }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      aria-describedby={describedBy}
      onClick={() => {
        onCheckedChange(!checked)
      }}
      className={cn(
        // 44px tall hit area around a 28px track, so the touch target clears
        // the minimum without the control looking oversized.
        'inline-flex h-11 w-14 shrink-0 items-center rounded-full p-1 transition-colors duration-150 ease-out',
        'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
        checked ? 'bg-primary' : 'bg-muted',
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'size-6 rounded-full bg-surface shadow-sm transition-transform duration-150 ease-out',
          checked ? 'translate-x-6' : 'translate-x-0',
        )}
      />
    </button>
  )
}
