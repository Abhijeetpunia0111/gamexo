import { useEffect, useState } from 'react'

/** True while the tablet is held landscape, re-evaluated on every rotation.
 *
 *  Layout alone can be handled with `lg:` variants, but some of what orientation decides
 *  isn't expressible in CSS — chiefly whether an input opens the system keyboard or defers
 *  to the app's own on-screen one — so the orientation has to exist in React state too. */
export function useIsLandscape() {
  const [landscape, setLandscape] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(orientation: landscape)').matches,
  )

  useEffect(() => {
    const mq = window.matchMedia('(orientation: landscape)')
    const sync = () => setLandscape(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])

  return landscape
}
