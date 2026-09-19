import type { ActivitySuitability } from '@/types'
import { formatActivity, sortActivities } from '@/utils/domain'

export interface ActivityBarsProps {
  activities: ActivitySuitability[]
}

/**
 * Activity suitability — FDS §6.4.
 *
 * Renders **whatever categories arrive**. The three v1 values are not
 * hardcoded: new categories are additive (API Spec §12), and a hardcoded list
 * would silently drop them.
 *
 * `indoor_museum` is given equal prominence to the outdoor scores rather than
 * being tucked underneath. For a family planner a rainy day is not a lost day,
 * it is a museum day — demoting the indoor score would hide the answer they
 * came for (FDS §2.2).
 */
export function ActivityBars({ activities }: ActivityBarsProps) {
  if (activities.length === 0) return null

  return (
    <ul className="flex flex-col gap-4">
      {sortActivities(activities).map((activity) => {
        const label = formatActivity(activity.activity)
        const score = Math.max(0, Math.min(100, Math.round(activity.score)))

        return (
          <li key={activity.activity} className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-3">
              <span className="truncate text-body-sm text-foreground">{label}</span>
              <span className="tabular text-body-sm text-muted-foreground">{score}</span>
            </div>

            <div
              role="meter"
              aria-valuenow={score}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${label}, ${String(score)} out of 100`}
              className="h-2 w-full overflow-hidden rounded-full bg-muted"
            >
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-[400ms] ease-out"
                style={{ width: `${String(score)}%` }}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
