import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import PlayerDetails from './booking/steps/PlayerDetails'
import { emptyDraft, type Draft } from './booking/types'

function Preview() {
  const [draft, setDraftState] = useState<Draft>(emptyDraft())
  const setDraft = (patch: Partial<Draft>) => setDraftState((d) => ({ ...d, ...patch }))
  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-page">
      <main className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-[clamp(1.25rem,3vw,3rem)] py-[clamp(1rem,2vw,1.5rem)]">
        <PlayerDetails draft={draft} setDraft={setDraft} />
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Preview />
  </StrictMode>,
)
