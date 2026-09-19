import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'

import { cn } from '@/lib/utils'

/**
 * Modal / sheet — FDS §11.5.
 *
 * Radix Dialog underneath, which gives focus trapping, Escape-to-close, focus
 * restoration to the trigger, and `aria-modal` semantics for free — all of
 * which FDS §14.2 requires and all of which are laborious and easy to get
 * subtly wrong by hand.
 *
 * `variant` covers the responsive presentation the design calls for: a day
 * detail is a centred modal at `lg`, a bottom sheet at `md`, and a full route
 * at `sm`. The first two are this component; the third is routing.
 */
export function Modal(props: ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root {...props} />
}

export function ModalTrigger(props: ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger {...props} />
}

export function ModalClose(props: ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close {...props} />
}

function ModalOverlay({ className, ...props }: ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      className={cn(
        'fixed inset-0 z-50 bg-overlay',
        'data-[state=closed]:animate-out data-[state=open]:animate-in',
        'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        className,
      )}
      {...props}
    />
  )
}

export interface ModalContentProps
  // `title` is replaced: the DOM attribute is a string, but a dialog heading
  // may legitimately be composed nodes.
  extends Omit<ComponentProps<typeof DialogPrimitive.Content>, 'title'> {
  /** Centred dialog, or a sheet anchored to an edge. */
  variant?: 'center' | 'bottom' | 'right'
  /** Required: every dialog needs an accessible name. */
  title: ReactNode
  /** Optional supporting line, wired to `aria-describedby`. */
  description?: ReactNode
  showCloseButton?: boolean
}

const VARIANT_CLASSES = {
  center: cn(
    'top-1/2 left-1/2 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl',
    'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
  ),
  bottom: cn(
    'inset-x-0 bottom-0 max-h-[85vh] rounded-t-xl',
    'data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom',
  ),
  right: cn(
    'inset-y-0 right-0 w-full max-w-md',
    'data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right',
  ),
} as const

export function ModalContent({
  className,
  variant = 'center',
  title,
  description,
  showCloseButton = true,
  children,
  ...props
}: ModalContentProps) {
  return (
    <DialogPrimitive.Portal>
      <ModalOverlay />
      <DialogPrimitive.Content
        className={cn(
          'fixed z-50 overflow-y-auto border border-border bg-surface p-6 shadow-lg',
          'data-[state=closed]:animate-out data-[state=open]:animate-in',
          'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
          VARIANT_CLASSES[variant],
          className,
        )}
        {...props}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <DialogPrimitive.Title className="text-h3 font-semibold text-heading">
              {title}
            </DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="text-body-sm text-muted-foreground">
                {description}
              </DialogPrimitive.Description>
            ) : (
              // Radix warns when a dialog has no description; this satisfies it
              // without inventing copy that would just repeat the title.
              <DialogPrimitive.Description className="sr-only">
                {typeof title === 'string' ? title : 'Dialog'}
              </DialogPrimitive.Description>
            )}
          </div>

          {showCloseButton ? (
            <DialogPrimitive.Close
              className={cn(
                'rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground',
                'transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
              )}
            >
              <X className="size-4" aria-hidden="true" />
              <span className="sr-only">Close</span>
            </DialogPrimitive.Close>
          ) : null}
        </div>

        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}
