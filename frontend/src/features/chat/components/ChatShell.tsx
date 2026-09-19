import * as DialogPrimitive from '@radix-ui/react-dialog'
import { Menu, PanelRight, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useLocation } from 'react-router'

import { APP_WORDMARK } from '@/constants/app'
import { cn } from '@/lib/utils'
import { ConversationHistoryPanel } from './ConversationHistoryPanel'

export interface ChatShellProps {
  children: ReactNode
  /** The trip identity band, pinned above the scrolling transcript. */
  header?: ReactNode
  /** The intelligence layer. Permanent at `xl`, a sheet below it, and absent
   * entirely until the trip is established — the layout collapses to two
   * zones rather than reserving an empty column. */
  sidebar?: ReactNode
}

/**
 * Three zones at `xl`: conversation history, the conversation workspace, and
 * the intelligence layer. Two at `lg`, one at `md` and below, where both
 * side panels become sheets reachable from the top bar.
 *
 * The workspace column owns its own scroll so the identity band and the
 * composer stay put while the transcript moves under them — the composer is
 * never pushed off-screen, and the trip's identity never scrolls away.
 */
export function ChatShell({ children, header, sidebar }: ChatShellProps) {
  const [historyOpen, setHistoryOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { pathname } = useLocation()

  // Selecting a conversation in a drawer is a route change — close the sheet
  // behind it rather than leaving it open over the newly-navigated page.
  // Adjusted during render (React's own "reset state when a prop changes"
  // pattern) so it takes effect before the stale sheet ever paints.
  const [lastPathname, setLastPathname] = useState(pathname)
  if (pathname !== lastPathname) {
    setLastPathname(pathname)
    setHistoryOpen(false)
    setSidebarOpen(false)
  }

  return (
    <div className="flex h-dvh w-full bg-background">
      <a
        href="#chat-main"
        className="skip-link rounded-md bg-primary px-4 py-2 text-body-sm font-medium text-primary-foreground"
      >
        Skip to conversation
      </a>

      <aside className="hidden w-[17rem] shrink-0 border-r border-border bg-surface-sunken lg:block">
        <ConversationHistoryPanel />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Compact bar below `lg` — the entry point to both side panels. */}
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-3 lg:hidden">
          <button
            type="button"
            onClick={() => {
              setHistoryOpen(true)
            }}
            className="flex size-11 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            aria-label="Open conversation history"
          >
            <Menu className="size-5" aria-hidden="true" />
          </button>

          <span className="text-h4 font-bold">
            <span className="text-heading">{APP_WORDMARK.primary}</span>
            <span className="text-primary">{APP_WORDMARK.secondary}</span>
          </span>

          {sidebar ? (
            <button
              type="button"
              onClick={() => {
                setSidebarOpen(true)
              }}
              className="ml-auto flex size-11 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
              aria-label="Open trip intelligence"
            >
              <PanelRight className="size-5" aria-hidden="true" />
            </button>
          ) : null}
        </header>

        <div className="flex min-h-0 flex-1">
          <main
            id="chat-main"
            tabIndex={-1}
            className="flex min-h-0 min-w-0 flex-1 flex-col focus:outline-none"
          >
            {header ? <div className="shrink-0 border-b border-border">{header}</div> : null}
            {children}
          </main>

          {sidebar ? (
            <aside className="hidden w-[21rem] shrink-0 overflow-y-auto border-l border-border bg-surface-sunken px-5 py-6 xl:block">
              {sidebar}
            </aside>
          ) : null}
        </div>
      </div>

      <SheetPanel
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        side="left"
        title="Conversation history"
        description="Your past trips, and a way to start a new one."
      >
        <ConversationHistoryPanel />
      </SheetPanel>

      {sidebar ? (
        <SheetPanel
          open={sidebarOpen}
          onOpenChange={setSidebarOpen}
          side="right"
          title="Trip intelligence"
          description="Weather, places and packing for this trip."
        >
          <div className="h-full overflow-y-auto px-5 py-6">{sidebar}</div>
        </SheetPanel>
      ) : null}
    </div>
  )
}

function SheetPanel({
  open,
  onOpenChange,
  side,
  title,
  description,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  side: 'left' | 'right'
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className={cn(
            'fixed inset-0 z-50 bg-overlay xl:hidden',
            'data-[state=closed]:animate-out data-[state=open]:animate-in',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            side === 'left' && 'lg:hidden',
          )}
        />
        <DialogPrimitive.Content
          className={cn(
            'fixed inset-y-0 z-50 w-[86%] max-w-sm bg-surface shadow-lg',
            'data-[state=closed]:animate-out data-[state=open]:animate-in',
            side === 'left'
              ? 'left-0 border-r border-border data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left lg:hidden'
              : 'right-0 border-l border-border data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right xl:hidden',
          )}
        >
          <DialogPrimitive.Title className="sr-only">{title}</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            {description}
          </DialogPrimitive.Description>
          <DialogPrimitive.Close
            className={cn(
              'absolute top-3 right-3 z-10 flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground',
              'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
            )}
          >
            <X className="size-4" aria-hidden="true" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
