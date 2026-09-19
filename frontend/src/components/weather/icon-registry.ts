import {
  Check,
  Cloud,
  CloudFog,
  CloudLightning,
  CloudRain,
  CloudRainWind,
  CloudSun,
  CircleAlert,
  CircleHelp,
  Snowflake,
  Sun,
  ThermometerSnowflake,
  ThermometerSun,
  TriangleAlert,
  Wind,
  X,
  type LucideIcon,
} from 'lucide-react'

import type { IconName } from '@/constants/domain'

/**
 * Icon-name → component registry.
 *
 * `constants/domain.ts` stores icon *names* rather than components, so that the
 * enum-to-presentation maps stay free of React imports and can be read by
 * anything — including tests and future non-DOM consumers. This module is the
 * one place that turns a name into a renderable icon.
 *
 * The map is explicit rather than a dynamic `lucide-react/dynamic` import,
 * because an explicit map tree-shakes: the bundle carries the sixteen icons the
 * product actually uses, not the whole library.
 */
const REGISTRY: Record<string, LucideIcon> = {
  // Risk, severity and advisory
  check: Check,
  'circle-alert': CircleAlert,
  'triangle-alert': TriangleAlert,
  x: X,
  'circle-help': CircleHelp,

  // Weather conditions
  sun: Sun,
  'cloud-sun': CloudSun,
  cloud: Cloud,
  'cloud-rain': CloudRain,
  'cloud-rain-wind': CloudRainWind,
  'cloud-lightning': CloudLightning,
  snowflake: Snowflake,
  'cloud-fog': CloudFog,

  // Risk factor types
  'thermometer-sun': ThermometerSun,
  'thermometer-snowflake': ThermometerSnowflake,
  wind: Wind,
}

/**
 * Resolve an icon name. Total by design: an unrecognised name — which is what a
 * new backend enum value produces — falls back to a neutral glyph rather than
 * rendering `undefined` and crashing the tree (API Spec §12).
 */
export function resolveIcon(name: IconName): LucideIcon {
  return REGISTRY[name] ?? CircleHelp
}
