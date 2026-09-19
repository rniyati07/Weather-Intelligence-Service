import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Compose class names, resolving Tailwind conflicts last-wins.
 *
 * `clsx` handles conditionals and arrays; `twMerge` resolves collisions, so a
 * caller's `className="p-8"` reliably beats a component's internal `p-6`
 * instead of depending on stylesheet order. Named `cn` because that is the
 * shadcn/ui convention and generated components import it by that name.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/** Descriptive alias for `cn`, for call sites that read better spelled out. */
export const mergeClasses = cn
