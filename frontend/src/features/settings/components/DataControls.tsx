import { useCallback, useId, useState } from 'react'

import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { SectionTitle } from '@/components/common/SectionTitle'
import { STORAGE_KEYS } from '@/constants/storage'
import { clearNamespace, measureNamespace, readStorage, removeStorage } from '@/services/storage'
import type { RecentSearch } from '@/types'
import { formatBytes } from '@/utils/format'
import { SettingRow } from './SettingRow'

/** Everything this app writes shares one namespace prefix. */
const APP_STORAGE_PREFIX = 'wis:'

interface StorageSnapshot {
  recentSearches: number
  geocodeBytes: number
  packingBytes: number
}

function readSnapshot(): StorageSnapshot {
  const searches = readStorage<RecentSearch[]>(STORAGE_KEYS.recentSearches, [])

  return {
    recentSearches: Array.isArray(searches) ? searches.length : 0,
    geocodeBytes: measureNamespace(STORAGE_KEYS.geocodeCache),
    packingBytes: measureNamespace(`${STORAGE_KEYS.packingChecklist}:`),
  }
}

/**
 * Data controls — FDS §5.5.
 *
 * Everything the product stores is on this device and nowhere else, so this is
 * the whole of "data control": show what is held, and let it be deleted.
 *
 * Counts are read on mount and re-read after each action rather than tracked in
 * state. The values come from `localStorage`, which another tab can change
 * underneath us — recomputing is both simpler and more truthful than mirroring.
 */
export function DataControls() {
  const [snapshot, setSnapshot] = useState<StorageSnapshot>(readSnapshot)
  const [lastAction, setLastAction] = useState<string | null>(null)
  const statusId = useId()

  const act = useCallback((message: string, perform: () => void) => {
    perform()
    setSnapshot(readSnapshot())
    setLastAction(message)
  }, [])

  const hasPacking = snapshot.packingBytes > 0

  return (
    <section className="flex flex-col gap-5">
      <SectionTitle>Data controls</SectionTitle>

      <Card className="flex flex-col divide-y divide-border">
        <SettingRow
          title="Recent searches"
          description={
            snapshot.recentSearches === 0
              ? 'No saved searches on this device.'
              : `${String(snapshot.recentSearches)} saved ${snapshot.recentSearches === 1 ? 'search' : 'searches'} on this device.`
          }
          control={
            <Button
              variant="secondary"
              size="md"
              disabled={snapshot.recentSearches === 0}
              onClick={() => {
                act('Recent searches cleared.', () => {
                  removeStorage(STORAGE_KEYS.recentSearches)
                })
              }}
            >
              Clear
            </Button>
          }
        />

        <SettingRow
          title="Geocoding cache"
          description={
            snapshot.geocodeBytes === 0
              ? 'Nothing cached. Places are looked up as you search.'
              : `Cache size ${formatBytes(snapshot.geocodeBytes)}.`
          }
          control={
            <Button
              variant="secondary"
              size="md"
              disabled={snapshot.geocodeBytes === 0}
              onClick={() => {
                act('Geocoding cache cleared.', () => {
                  removeStorage(STORAGE_KEYS.geocodeCache)
                })
              }}
            >
              Clear cache
            </Button>
          }
        />

        {/* Only offered once there is something to clear — an always-present
            "clear everything" invites an accidental reset of settings too. */}
        {hasPacking ? (
          <SettingRow
            title="Packing checklists"
            description={`Ticked items saved for your trips — ${formatBytes(snapshot.packingBytes)}.`}
            control={
              <Button
                variant="secondary"
                size="md"
                onClick={() => {
                  act('Packing checklists cleared.', () => {
                    clearNamespace(`${STORAGE_KEYS.packingChecklist}:`)
                  })
                }}
              >
                Clear
              </Button>
            }
          />
        ) : null}
      </Card>

      {/* Announced rather than shown as a toast: the row's own description
          updates in place, and a screen-reader user needs the confirmation. */}
      <p id={statusId} aria-live="polite" className="text-body-sm text-muted-foreground">
        {lastAction}
      </p>

      <p className="text-body-sm text-subtle-foreground">
        Everything above is stored in this browser only. Clearing your browser data for this site
        removes all of it.
        <span className="sr-only"> Namespace: {APP_STORAGE_PREFIX}</span>
      </p>
    </section>
  )
}
