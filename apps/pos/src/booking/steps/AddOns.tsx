import { useState } from 'react'
import { useEquipment } from '../../api/hooks'
import { offersFor, unitsClaimed, type Offer } from '../offers'
import ProductCard from '../ProductCard'
import type { Draft } from '../types'

export default function AddOns({ draft, setDraft }: { draft: Draft; setDraft: (patch: Partial<Draft>) => void }) {
  const equipmentQuery = useEquipment()
  // General kit (no sport of its own) always shows; sport-linked kit only shows
  // for the sport actually being played.
  const items = (equipmentQuery.data ?? []).filter((i) => i.sportId === null || i.sportId === draft.sportId)
  // One card per offer, not per item: a shuttlecock shows as Rent / Buy / Pack of 6.
  const offers = items.flatMap(offersFor)
  const categories = ['All', ...new Set(items.map((i) => i.category).filter(Boolean))]
  const [category, setCategory] = useState('All')
  const shown = category === 'All' ? offers : offers.filter((o) => o.item.category === category)
  const gridColumns = Math.max(1, Math.ceil(shown.length / 2))

  const setQty = (key: string, qty: number, max: number) => {
    const next = { ...draft.equipment }
    if (qty > 0) next[key] = Math.min(qty, max)
    else delete next[key]
    setDraft({ equipment: next })
  }

  /** Offers of one item share a stock pool — a pack of six leaves six fewer to rent. */
  const headroomFor = (offer: Offer) => {
    const qty = draft.equipment[offer.key] || 0
    const spare = Math.floor((offer.item.stock - unitsClaimed(offers, draft.equipment, offer.item.id)) / offer.draws)
    return qty + Math.max(0, spare)
  }

  return (
    <div className="flex w-full flex-col gap-5">
      <div className="flex w-full items-center justify-between">
        <p className="text-[clamp(1rem,1.3vw,1.125rem)] font-medium text-ink">Need any kit?</p>
        <p className="text-[clamp(0.8125rem,1vw,0.875rem)] text-muted">Optional — skip if not needed</p>
      </div>

      {equipmentQuery.isPending ? (
        <p className="text-sm text-muted">Loading inventory…</p>
      ) : equipmentQuery.error ? (
        <p role="alert" className="text-sm text-negative">
          Could not load equipment: {equipmentQuery.error instanceof Error ? equipmentQuery.error.message : 'unknown error'}
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted">No equipment configured for sale yet.</p>
      ) : (
        <>
          {categories.length > 2 && (
            <div className="flex w-full flex-wrap gap-2">
              {categories.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCategory(c)}
                  className={`rounded-xl px-4 py-2 text-[clamp(0.8125rem,0.95vw,0.875rem)] font-semibold transition-colors ${
                    category === c ? 'bg-ink text-white' : 'bg-surface text-ink hover:bg-surface-muted'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          )}

          <div
            className="grid grid-flow-col grid-rows-2 gap-[clamp(0.75rem,1.6vw,1rem)] overflow-x-auto pb-2"
            style={{ gridTemplateColumns: `repeat(${gridColumns}, minmax(16rem, 1fr))` }}
          >
            {shown.map((offer) => {
              const max = headroomFor(offer)
              return (
                <ProductCard
                  key={offer.key}
                  offer={offer}
                  qty={draft.equipment[offer.key] || 0}
                  max={max}
                  onAdd={() => setQty(offer.key, 1, max)}
                  onQty={(qty) => setQty(offer.key, qty, max)}
                />
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
