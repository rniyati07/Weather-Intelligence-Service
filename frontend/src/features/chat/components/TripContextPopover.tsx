import { SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'

import { Modal, ModalContent, ModalTrigger } from '@/components/ui/modal'
import type { TripContextPayload } from '@/types'
import { formatDateRange, inclusiveDayCount, parseIsoDate } from '@/utils/date'
import { formatCoordinates, titleCaseSlug } from '@/utils/format'

export interface TripContextPopoverProps {
  trip: TripContextPayload
}

interface ContextRow {
  label: string
  value: string
}

/**
 * What the assistant currently understands about this trip.
 *
 * Strictly a read-out of `tripContext` as the backend last returned it — the
 * user changes it by saying so in the conversation, not by editing a form
 * here, which is why this is a disclosure and not an input surface. Rows for
 * fields the backend hasn't established are omitted entirely rather than
 * rendered empty.
 */
export function TripContextPopover({ trip }: TripContextPopoverProps) {
  const [open, setOpen] = useState(false)

  const rows = buildRows(trip)
  if (rows.length === 0) return null

  return (
    <Modal open={open} onOpenChange={setOpen}>
      <ModalTrigger
        className="inline-flex h-10 items-center gap-2 rounded-lg border border-border bg-surface px-3.5 text-body-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        aria-label="Show trip context"
      >
        <SlidersHorizontal className="size-4" aria-hidden="true" />
        Trip context
      </ModalTrigger>

      <ModalContent
        title="Trip context"
        description="What I've understood so far. Tell me in the conversation to change any of it."
      >
        <dl className="flex flex-col">
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex items-baseline justify-between gap-6 border-b border-border py-2.5 last:border-b-0"
            >
              <dt className="text-body-sm text-muted-foreground">{row.label}</dt>
              <dd className="min-w-0 text-right text-body-sm font-medium text-heading">
                {row.value}
              </dd>
            </div>
          ))}
        </dl>
      </ModalContent>
    </Modal>
  )
}

function buildRows(trip: TripContextPayload): ContextRow[] {
  const rows: ContextRow[] = []
  const { destination, startDate, endDate, interests, travelStyle, pace } = trip

  if (destination) {
    rows.push({ label: 'Destination', value: destination.displayName })
    rows.push({
      label: 'Coordinates',
      value: formatCoordinates(destination.latitude, destination.longitude),
    })
    if (destination.timezone) rows.push({ label: 'Timezone', value: destination.timezone })
  }

  if (startDate && endDate) {
    rows.push({ label: 'Dates', value: formatDateRange(startDate, endDate) })
    const start = parseIsoDate(startDate)
    const end = parseIsoDate(endDate)
    if (start && end) {
      const days = inclusiveDayCount(start, end)
      rows.push({ label: 'Duration', value: `${String(days)} ${days === 1 ? 'day' : 'days'}` })
    }
  }

  if (interests && interests.length > 0) {
    rows.push({ label: 'Interests', value: interests.map(titleCaseSlug).join(', ') })
  }
  if (travelStyle) rows.push({ label: 'Travelling as', value: titleCaseSlug(travelStyle) })
  if (pace) rows.push({ label: 'Pace', value: titleCaseSlug(pace) })

  return rows
}
