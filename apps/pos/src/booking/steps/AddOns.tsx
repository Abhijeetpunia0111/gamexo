import { useState } from 'react'
import { ImageOff } from 'lucide-react'
import { useEquipment, type EquipmentItem } from '../../api/hooks'
import { money } from '../../lib/format'
import type { Draft } from '../types'
import addIcon from '../../assets/figma/shop/add.svg'
import removeIcon from '../../assets/figma/shop/remove.svg'

function ProductCard({
  item,
  qty,
  onAdd,
  onQty,
}: {
  item: EquipmentItem
  qty: number
  onAdd: () => void
  onQty: (qty: number) => void
}) {
  const soldOut = item.stock <= 0
  const active = qty > 0
  const atLimit = qty >= item.stock

  return (
    <div
      role="button"
      tabIndex={soldOut ? -1 : 0}
      aria-disabled={soldOut}
      aria-label={qty === 0 ? `Add ${item.name}` : undefined}
      onClick={() => !active && !soldOut && onAdd()}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !active && !soldOut) {
          e.preventDefault()
          onAdd()
        }
      }}
      className={`flex aspect-square w-full flex-col items-stretch gap-2.5 border-4 bg-surface p-[clamp(0.625rem,1.2vw,0.875rem)] text-left transition-colors ${
        active ? 'border-lime' : 'border-transparent'
      } ${soldOut ? 'cursor-not-allowed opacity-50' : !active ? 'cursor-pointer' : ''}`}
    >
      <div className="relative w-full flex-1 overflow-hidden">
        {item.imageUrl ? (
          <img src={item.imageUrl} alt="" className="size-full object-contain" />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-1 bg-surface-muted text-muted">
            <ImageOff size={18} strokeWidth={1.5} />
            <span className="text-[11px] font-medium">No image</span>
          </div>
        )}

        {active && (
          <div
            onClick={(e) => e.stopPropagation()}
            className="absolute bottom-1.5 right-1.5 flex items-center gap-1.5 rounded-lg bg-[#202020] px-2 py-1.5 shadow-[0px_8px_11px_-6px_rgba(0,0,0,0.12)]"
          >
            <button
              type="button"
              aria-label={`Remove one ${item.name}`}
              onClick={() => onQty(qty - 1)}
              className="flex size-4 items-center justify-center text-white"
            >
              <img src={removeIcon} alt="" className="size-full" />
            </button>
            <span className="w-3 text-center text-[11px] font-semibold text-white">{qty}</span>
            <button
              type="button"
              aria-label={`Add one more ${item.name}`}
              disabled={atLimit}
              onClick={() => onQty(qty + 1)}
              className="flex size-4 items-center justify-center text-white disabled:opacity-40"
            >
              <img src={addIcon} alt="" className="size-full" />
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-0.5">
        <p className="text-[clamp(0.8125rem,1vw,0.9375rem)] font-bold leading-tight text-ink">{item.name}</p>
        <p className="text-[clamp(0.75rem,0.9vw,0.8125rem)] font-medium text-muted">
          {soldOut ? 'Sold out' : money(item.price)}
        </p>
      </div>
    </div>
  )
}

export default function AddOns({ draft, setDraft }: { draft: Draft; setDraft: (patch: Partial<Draft>) => void }) {
  const equipmentQuery = useEquipment()
  // General kit (no sport of its own) always shows; sport-linked kit only shows
  // for the sport actually being played.
  const items = (equipmentQuery.data ?? []).filter((i) => i.sportId === null || i.sportId === draft.sportId)
  const categories = ['All', ...new Set(items.map((i) => i.category).filter(Boolean))]
  const [category, setCategory] = useState('All')
  const shown = category === 'All' ? items : items.filter((i) => i.category === category)
  const gridColumns = Math.max(1, Math.ceil(shown.length / 2))

  const setQty = (id: string, qty: number, max: number) => {
    const next = { ...draft.equipment }
    if (qty > 0) next[id] = Math.min(qty, max)
    else delete next[id]
    setDraft({ equipment: next })
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
            {shown.map((item) => (
              <ProductCard
                key={item.id}
                item={item}
                qty={draft.equipment[item.id] || 0}
                onAdd={() => setQty(item.id, 1, item.stock)}
                onQty={(qty) => setQty(item.id, qty, item.stock)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
