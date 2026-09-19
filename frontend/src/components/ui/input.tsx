import * as LabelPrimitive from '@radix-ui/react-label'
import type { ComponentProps } from 'react'
import { useId } from 'react'

import { cn } from '@/lib/utils'

/**
 * Input — FDS §9.11, §14.6.
 *
 * 44px tall, so it clears the minimum touch target at every breakpoint.
 *
 * The label is a required prop rather than an optional one. FDS §9.11 is
 * explicit that placeholders are never labels, and making the label optional is
 * how a form ends up with three unlabelled fields nobody noticed until the
 * screen-reader pass.
 */
export interface InputProps extends Omit<ComponentProps<'input'>, 'id'> {
  /** Always rendered and always visible. Pass `hideLabel` for a visual-only exception. */
  label: string
  /** Visually hides the label while keeping it for assistive tech. Use sparingly. */
  hideLabel?: boolean
  /** Validation message. Sets `aria-invalid` and is announced via `aria-describedby`. */
  error?: string | undefined
  /** Persistent helper text below the control. */
  hint?: string | undefined
  id?: string
}

export function Input({
  className,
  label,
  hideLabel = false,
  error,
  hint,
  id: providedId,
  ...props
}: InputProps) {
  const generatedId = useId()
  const id = providedId ?? generatedId
  const errorId = `${id}-error`
  const hintId = `${id}-hint`

  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ')

  return (
    <div className="flex w-full flex-col gap-1.5">
      <Label htmlFor={id} className={cn(hideLabel && 'sr-only')}>
        {label}
      </Label>

      <input
        id={id}
        data-slot="input"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={cn(
          'h-11 w-full rounded-md border border-input bg-surface px-3 text-foreground placeholder:text-subtle-foreground',
          'text-body transition-colors duration-150 ease-out outline-none',
          'focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40',
          'disabled:cursor-not-allowed disabled:bg-muted disabled:text-subtle-foreground',
          error && 'border-destructive focus-visible:border-destructive',
          className,
        )}
        {...props}
      />

      {hint ? (
        <p id={hintId} className="text-body-sm text-muted-foreground">
          {hint}
        </p>
      ) : null}

      {/* Announced on change, but politely — a validation message should not
          interrupt a user mid-keystroke. */}
      {error ? (
        <p id={errorId} role="alert" className="text-body-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}

export function Label({ className, ...props }: ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn(
        'text-body-sm font-medium text-muted-foreground select-none',
        'peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
        className,
      )}
      {...props}
    />
  )
}
