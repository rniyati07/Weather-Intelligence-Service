/**
 * Feature modules — the bulk of the application.
 *
 * Import rule, and the one that keeps this structure from collapsing: a feature
 * may import from `components/`, `hooks/`, `lib/`, `utils/`, `constants/` and
 * `types/`, but **never from another feature**. When two features need the same
 * thing, it is promoted to `components/` or `hooks/` rather than reached across
 * for. That is what stops the dependency graph turning into a mesh.
 *
 * The rule currently holds with no exceptions. `features/shared/` existed only
 * to hold the placeholder notice the unbuilt screens rendered; it was deleted
 * once About and Settings were real. If a genuine cross-feature need appears,
 * promote to `components/` or `hooks/` rather than reintroducing it.
 */

export { AboutPage } from './about/pages/AboutPage'
export { ResultsPage } from './dashboard/pages/ResultsPage'
export { NotFoundPage } from './not-found/pages/NotFoundPage'
export { PlannerPage } from './planner/pages/PlannerPage'
export { SettingsPage } from './settings/pages/SettingsPage'
