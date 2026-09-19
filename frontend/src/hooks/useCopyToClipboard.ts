import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Copy text and report success briefly.
 *
 * Exists because `requestId` is click-to-copy in the metadata strip and in
 * every error state — a user quoting it to support is the whole point of
 * surfacing it. The `copied` flag drives the icon morphing to a check for
 * 1.5s (FDS §11.8).
 */
export function useCopyToClipboard(resetAfterMs = 1500) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    return () => {
      if (timerRef.current !== undefined) window.clearTimeout(timerRef.current)
    }
  }, [])

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      try {
        await navigator.clipboard.writeText(text)
        setCopied(true)

        if (timerRef.current !== undefined) window.clearTimeout(timerRef.current)
        timerRef.current = window.setTimeout(() => setCopied(false), resetAfterMs)

        return true
      } catch {
        // Denied permission, or a non-secure context. The caller decides
        // whether that is worth telling the user about.
        setCopied(false)
        return false
      }
    },
    [resetAfterMs],
  )

  return { copied, copy }
}
