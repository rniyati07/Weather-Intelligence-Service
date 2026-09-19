import { Slot } from '@radix-ui/react-slot'
import type { VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'
import { buttonVariants } from './variants'

export interface ButtonProps extends ComponentProps<'button'>, VariantProps<typeof buttonVariants> {
  /** Render as the child element instead of a `<button>` — for links styled as buttons. */
  asChild?: boolean
  /** Swaps the label for a spinner. Width is preserved to prevent layout shift. */
  loading?: boolean
}

/**
 * Button — FDS §9.10.
 *
 * Variants and sizes live in `./variants`; this file owns behaviour only. The
 * loading state is the one piece worth explaining: the label stays in the DOM
 * but invisible, so the button keeps its width and does not resize mid-action,
 * while `sr-only` preserves the accessible name that the spinner would
 * otherwise replace with nothing.
 */
export function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot : 'button'
  // `Slot` forwards to a single child, so the spinner treatment — which wraps
  // the label in extra elements — only applies to a real <button>.
  const showSpinner = loading && !asChild

  return (
    <Component
      data-slot="button"
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled ?? loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {showSpinner ? (
        <>
          <Loader2 className="animate-spin" aria-hidden="true" />
          <span className="sr-only">{children}</span>
          <span aria-hidden="true" className="invisible">
            {children}
          </span>
        </>
      ) : (
        children
      )}
    </Component>
  )
}
