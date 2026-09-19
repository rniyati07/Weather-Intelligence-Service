import { useId } from 'react'

import { UnitsToggle } from '@/components/common/UnitsToggle'
import { SectionTitle } from '@/components/common/SectionTitle'
import { PageContainer } from '@/components/layout/PageContainer'
import { Card } from '@/components/ui/card'
import { APP_NAME } from '@/constants/app'
import { usePreferences } from '@/hooks/usePreferences'
import { env } from '@/lib/env'
import { DataControls } from '../components/DataControls'
import { SettingRow } from '../components/SettingRow'
import { Switch } from '../components/Switch'

/**
 * Settings — `/settings`. FDS §5.5.
 *
 * Preferences and data control, nothing else. Every value here is device-local:
 * there is no account, so "settings" means what this browser remembers.
 *
 * Deliberately narrow. A short, scannable column suits a page of independent
 * switches better than the 1280px product width, which would strand each
 * control at the far right of an otherwise empty row.
 */
export function SettingsPage() {
  const { temperatureUnit, reducedMotion, setReducedMotion } = usePreferences()

  const unitsDescriptionId = useId()
  const languageDescriptionId = useId()
  const motionDescriptionId = useId()
  const languageId = useId()

  return (
    <PageContainer
      // A measured column rather than `prose` (70ch) or the 1280px product
      // width: `prose` is sized for running text and squeezes a label-plus-
      // control row onto two lines, while the full width strands every control
      // at the far right of an empty row. `Container` supplies `mx-auto`.
      width="full"
      className="max-w-[52rem]"
      title="Settings"
      description="Preferences are stored on this device only."
    >
      <div className="flex flex-col gap-12">
        <section className="flex flex-col gap-5">
          <SectionTitle>Preferences</SectionTitle>

          <Card className="flex flex-col divide-y divide-border">
            <SettingRow
              title="Units"
              description="Applies to every temperature across the product."
              descriptionId={unitsDescriptionId}
              control={<UnitsToggle />}
            />

            <SettingRow
              title="Language"
              description="Only English is available in v1. More languages are planned."
              descriptionId={languageDescriptionId}
              control={
                /* Disabled, with the reason stated beside it. The alternative —
                 * listing languages the API would reject with a 400 — offers a
                 * choice the product cannot honour (FDS §5.5). */
                <select
                  id={languageId}
                  aria-label="Narration language"
                  aria-describedby={languageDescriptionId}
                  disabled
                  value="en"
                  onChange={() => undefined}
                  className="h-11 min-w-[16rem] rounded-md border border-input bg-surface px-3 text-body text-muted-foreground disabled:cursor-not-allowed"
                >
                  <option value="en">English (only language in v1)</option>
                </select>
              }
            />

            <SettingRow
              title="Reduced motion"
              description="Meters render filled, count-ups show final values, and shimmer becomes a static tint."
              descriptionId={motionDescriptionId}
              control={
                <Switch
                  checked={reducedMotion}
                  onCheckedChange={setReducedMotion}
                  label="Reduced motion"
                  describedBy={motionDescriptionId}
                />
              }
            />
          </Card>

          {/* Stated because the toggle is additive, not authoritative — someone
              who already set this at OS level should not think switching it off
              here will bring animation back. */}
          <p className="text-body-sm text-subtle-foreground">
            If your device already requests reduced motion, that is respected whether or not this is
            on. Currently showing temperatures in{' '}
            {temperatureUnit === 'celsius' ? 'Celsius' : 'Fahrenheit'}.
          </p>
        </section>

        <DataControls />

        <section className="flex flex-col gap-5">
          <SectionTitle>About this build</SectionTitle>

          <Card className="flex flex-col divide-y divide-border">
            <SettingRow
              title={APP_NAME}
              description="The version of the interface you are running."
              control={
                <span className="tabular text-body text-muted-foreground">v{env.appVersion}</span>
              }
            />
          </Card>
        </section>
      </div>
    </PageContainer>
  )
}
