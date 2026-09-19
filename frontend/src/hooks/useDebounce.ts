import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Debounce a value.
 *
 * Used for the destination search (300ms) and date-range changes (400ms). This
 * is not only a UX nicety: the API allows 60 requests a minute, and a user
 * dragging a date range would otherwise stack a request per frame.
 */
export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}

/**
 * Debounce a callback. The returned function is stable, and the latest
 * callback is always the one invoked — so a stale closure can't fire.
 */
export function useDebouncedCallback<TArgs extends unknown[]>(
  callback: (...args: TArgs) => void,
  delayMs: number,
): (...args: TArgs) => void {
  const callbackRef = useRef(callback)
  const delayRef = useRef(delayMs)
  const timerRef = useRef<number | undefined>(undefined)

  // Read through refs so the returned function can stay identity-stable while
  // still invoking the newest callback and honouring the newest delay.
  useEffect(() => {
    callbackRef.current = callback
    delayRef.current = delayMs
  }, [callback, delayMs])

  useEffect(() => {
    return () => {
      if (timerRef.current !== undefined) window.clearTimeout(timerRef.current)
    }
  }, [])

  // Empty deps: the identity must never change, or every consumer that passes
  // this to a child re-renders it on each keystroke.
  return useCallback((...args: TArgs) => {
    if (timerRef.current !== undefined) window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => callbackRef.current(...args), delayRef.current)
  }, [])
}
