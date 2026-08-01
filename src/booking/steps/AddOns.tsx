import { Minus, Plus, ShoppingBag } from 'lucide-react'
import { equipmentForSport, money, type Draft } from '../../data/booking'

export default function AddOns({ draft, setDraft }: { draft: Draft; setDraft: (patch: Partial<Draft>) => void }) {
  const items = equipmentForSport(draft.sportId || '')

  const setQty = (id: string, qty: number) => {
    const next = { ...draft.equipment }
    if (qty > 0) next[id] = qty
    else delete next[id]
    setDraft({ equipment: next })
  }

  const trayCount = Object.values(draft.equipment).reduce((a, b) => a + b, 0)
  const trayTotal = items.reduce((sum, item) => sum + (draft.equipment[item.id] || 0) * item.price, 0)

  return (
    <div className="flex w-full flex-col gap-5">
      <p className="text-xl text-ink">Need any kit?</p>

      <div className="grid w-full grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
        {items.map((item) => {
          const qty = draft.equipment[item.id] || 0
          return (
            <div
              key={item.id}
              className={`flex flex-col items-start gap-3 rounded-xl border bg-surface p-4 transition-colors ${
                qty > 0 ? 'border-ink' : 'border-border-card'
              }`}
            >
              <div className="flex size-9 items-center justify-center rounded-full bg-surface-muted text-ink">
                <ShoppingBag size={16} />
              </div>
              <div className="flex flex-col gap-0.5">
                <p className="text-sm font-semibold text-ink">{item.name}</p>
                <p className="text-xs text-muted">{item.hint}</p>
                <p className="text-sm font-medium text-positive">{money(item.price)}</p>
              </div>

              {qty === 0 ? (
                <button
                  type="button"
                  onClick={() => setQty(item.id, 1)}
                  className="mt-1 flex h-8 w-full items-center justify-center gap-1.5 rounded-lg border border-border-input bg-white text-sm text-ink"
                >
                  <Plus size={14} /> Add
                </button>
              ) : (
                <div className="mt-1 flex h-8 w-full items-center justify-between rounded-lg bg-ink px-2 text-bone">
                  <button type="button" onClick={() => setQty(item.id, qty - 1)} className="flex size-6 items-center justify-center">
                    <Minus size={14} />
                  </button>
                  <span className="text-sm">{qty}</span>
                  <button type="button" onClick={() => setQty(item.id, qty + 1)} className="flex size-6 items-center justify-center">
                    <Plus size={14} />
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {trayCount > 0 && (
        <div className="flex w-full items-center justify-between rounded-xl bg-white p-4">
          <p className="text-sm text-slate">
            {trayCount} item{trayCount > 1 ? 's' : ''} added
          </p>
          <p className="text-base font-semibold text-ink">{money(trayTotal)}</p>
        </div>
      )}
    </div>
  )
}
