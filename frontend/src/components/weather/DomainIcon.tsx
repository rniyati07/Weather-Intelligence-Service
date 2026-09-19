import type { LucideProps } from 'lucide-react'
import { createElement } from 'react'

import type { IconName } from '@/constants/domain'
import { resolveIcon } from './icon-registry'

export interface DomainIconProps extends LucideProps {
  /** An icon name from `constants/domain` — a risk level, condition or factor type. */
  name: IconName
}

/**
 * Render an icon by its domain name.
 *
 * The indirection earns its keep by confining the registry lookup to one place.
 * `createElement` rather than a capitalised local and JSX: assigning a
 * component to a variable inside a render body is indistinguishable, to a
 * linter, from *defining* one there — and defining one there really would
 * remount the subtree on every render.
 *
 * Decorative by default: `aria-hidden`, with the meaning carried by adjacent
 * text (FDS §14.3). Pass `aria-hidden={false}` and a label only if an icon is
 * ever the sole carrier of information — which, by design, it should not be.
 */
export function DomainIcon({ name, ...props }: DomainIconProps) {
  return createElement(resolveIcon(name), { 'aria-hidden': true, ...props })
}
