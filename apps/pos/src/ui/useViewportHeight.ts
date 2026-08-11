import { useEffect } from 'react'

/** Publishes the genuinely visible viewport height as `--app-height` (see index.css).
 *
 *  `100dvh` already follows Safari's collapsing URL bar, but it does *not* react to the
 *  on-screen keyboard: iOS overlays the keyboard on top of the layout viewport instead of
 *  shrinking it, so a dvh-sized shell keeps its footer underneath the keys. `visualViewport`
 *  is the only thing that reports the box the counter can actually see and touch. */
export function useViewportHeight() {
  useEffect(() => {
    const viewport = window.visualViewport
    if (!viewport) return

    const sync = () => {
      document.documentElement.style.setProperty('--app-height', `${viewport.height}px`)
    }

    sync()
    viewport.addEventListener('resize', sync)
    return () => {
      viewport.removeEventListener('resize', sync)
      document.documentElement.style.removeProperty('--app-height')
    }
  }, [])
}
