import { useEffect, useState } from 'react'

import { BREAKPOINTS, type Breakpoint } from '@/constants/theme'

export interface WindowSize {
  width: number
  height: number
  breakpoint: Breakpoint
}

function currentBreakpoint(width: number): Breakpoint {
  if (width >= BREAKPOINTS.xl) return 'xl'
  if (width >= BREAKPOINTS.lg) return 'lg'
  if (width >= BREAKPOINTS.md) return 'md'
  return 'sm'
}

function read(): WindowSize {
  const width = window.innerWidth
  return { width, height: window.innerHeight, breakpoint: currentBreakpoint(width) }
}

/**
 * Viewport dimensions plus the active FDS breakpoint band.
 *
 * Prefer `useMediaQuery` / `useBreakpoint` for layout branching — they update
 * only when a threshold is actually crossed. Reach for this one when a
 * component needs the pixel value itself, such as sizing a carousel or a chart.
 *
 * Updates are throttled to one per animation frame; a resize drag fires
 * `resize` far faster than React can usefully re-render.
 */
export function useWindowSize(): WindowSize {
  const [size, setSize] = useState<WindowSize>(read)

  useEffect(() => {
    let frame = 0

    function handleResize() {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setSize(read()))
    }

    window.addEventListener('resize', handleResize)
    // Cover any resize that happened between the initial read and this effect.
    handleResize()

    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', handleResize)
    }
  }, [])

  return size
}
