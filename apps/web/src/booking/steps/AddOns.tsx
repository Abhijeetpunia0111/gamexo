import { Minus, Package, Plus } from 'lucide-react'
import { equipmentForSport, money, type Draft } from '../../data/booking'
import * as db from '../../lib/db'

export default function AddOns({ draft, setDraft }: { draft: Draft; setDraft: (patch: Partial<Draft>) => void }) {
  db.useDbVersion()
  const items = equipmentForSport(draft.sportId || '')

  const setQty = (id: string, qty: number, max: number) => {
    const next = { ...draft.equipment }
    if (qty > 0) next[id] = Math.min(qty, max)
    else delete next[id]
    setDraft({ equipment: next })
  }

  const trayCount = Object.values(draft.equipment).reduce((a, b) => a + b, 0)
  const trayTotal = items.reduce((sum, item) => sum + (draft.equipment[item.id] || 0) * item.price, 0)

  return (
    <div className="flex w-full flex-col gap-5">
      <p className="text-xl text-ink">Need any kit?</p>

      {items.length === 0 ? (
        <p className="text-sm text-muted">No equipment configured for sale yet.</p>
      ) : (
        <div className="grid w-full grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
          {items.map((item) => {
            const qty = draft.equipment[item.id] || 0
            const active = qty > 0
            const soldOut = item.stock <= 0
            const atLimit = qty >= item.stock

            const addFirst = () => {
              if (qty === 0 && !soldOut) setQty(item.id, 1, item.stock)
            }

            return (
              <div
                key={item.id}
                role="button"
                tabIndex={soldOut ? -1 : 0}
                aria-disabled={soldOut}
                aria-label={qty === 0 ? `Add ${item.name}` : undefined}
                onClick={addFirst}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    addFirst()
                  }
                }}
                className={`group relative flex flex-col items-start gap-3 rounded-xl border p-4 text-left transition-all ${
                  active ? 'border-ink bg-lime/10 shadow-sm' : 'border-border-card bg-surface hover:border-ink/25'
                } ${soldOut ? 'cursor-not-allowed opacity-50' : qty === 0 ? 'cursor-pointer' : ''}`}
              >
                {active && (
                  <span className="absolute -right-2 -top-2 flex size-6 items-center justify-center rounded-full bg-lime text-xs font-semibold text-lime-ink shadow-[0px_2px_6px_rgba(0,0,0,0.15)]">
                    {qty}
                  </span>
                )}

                <div
                  className={`flex size-10 items-center justify-center rounded-full transition-colors ${
                    active ? 'bg-lime text-lime-ink' : 'bg-surface-muted text-ink'
                  }`}
                >
                  <Package size={18} strokeWidth={1.75} />
                </div>

                <div className="flex flex-col gap-0.5">
                  <p className="text-sm font-semibold text-ink">{item.name}</p>
                  <p className="text-xs text-muted">{item.hint}</p>
                </div>

                <div className="flex w-full items-center justify-between">
                  <span className="text-sm font-medium text-positive">{money(item.price)}</span>

                  {active ? (
                    <span
                      role="group"
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-2.5 rounded-full bg-ink px-1.5 py-1 text-bone"
                    >
                      <button
                        type="button"
                        aria-label={`Remove one ${item.name}`}
                        onClick={() => setQty(item.id, qty - 1, item.stock)}
                        className="flex size-5 items-center justify-center"
                      >
                        <Minus size={12} />
                      </button>
                      <span className="w-3 text-center text-xs">{qty}</span>
                      <button
                        type="button"
                        aria-label={`Add one more ${item.name}`}
                        disabled={atLimit}
                        onClick={() => setQty(item.id, qty + 1, item.stock)}
                        className="flex size-5 items-center justify-center disabled:opacity-40"
                      >
                        <Plus size={12} />
                      </button>
                    </span>
                  ) : (
                    <span className={`text-xs ${soldOut ? 'text-negative' : item.stock <= 5 ? 'text-flame' : 'text-muted'}`}>
                      {soldOut ? 'Sold out' : `${item.stock} left`}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

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
