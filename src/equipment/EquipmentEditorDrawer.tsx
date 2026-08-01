import { useState } from 'react'
import { Edit3, Trash2, X } from 'lucide-react'
import type { Equipment as EquipmentItem } from '../data/booking'
import * as db from '../lib/db'

export default function EquipmentEditorDrawer({
  item,
  onClose,
  onSaved,
}: {
  item: EquipmentItem & { activeForSale: boolean }
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(item.name)
  const [hint, setHint] = useState(item.hint)
  const [price, setPrice] = useState(String(item.price))
  const [stock, setStock] = useState(String(item.stock))
  const [active, setActive] = useState(item.activeForSale)
  const [sports, setSports] = useState(item.sports)

  const save = () => {
    const fallback = { stock: item.stock, activeForSale: item.activeForSale, sports: item.sports }
    db.setEquipmentStock(item.id, Number(price) === item.price ? Number(stock) : Number(stock), fallback)
    db.setEquipmentActive(item.id, active, fallback)
    db.setEquipmentSports(item.id, sports, fallback)
    onSaved()
  }

  const remove = () => {
    db.setEquipmentActive(item.id, false, { stock: item.stock, activeForSale: item.activeForSale, sports: item.sports })
    onSaved()
  }

  return (
    <>
      <button type="button" aria-label="Close panel" onClick={onClose} className="fixed inset-0 z-40 bg-black/30" />
      <div className="fixed inset-y-0 right-0 z-50 flex h-screen w-full max-w-[520px] flex-col overflow-y-auto bg-page shadow-2xl">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border-soft px-5 py-4">
          <div>
            <p className="text-base font-semibold text-ink">Edit item</p>
            <p className="text-sm text-slate">Change price, stock, linked sports, or remove it from sale.</p>
          </div>
          <button type="button" onClick={onClose} className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border-input bg-white">
            <X size={16} className="text-ink" />
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-5 p-5">
          <div className="rounded-2xl border border-border-card bg-white p-4 shadow-sm">
            <p className="text-sm font-semibold text-ink">Preview</p>
            <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-border-input bg-surface p-4">
              <div>
                <p className="text-lg font-semibold text-ink">{item.name}</p>
                <p className="mt-1 text-sm text-slate">{item.hint}</p>
              </div>
              <button type="button" className="flex h-10 w-10 items-center justify-center rounded-full border border-border-input bg-white text-slate">
                <Edit3 size={18} />
              </button>
            </div>
          </div>

          <div className="grid gap-4">
            <label className="flex flex-col gap-2 text-sm">
              <span className="font-medium text-ink">Name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} className="rounded-xl border border-border-input bg-white px-4 py-3 text-sm text-ink" />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="font-medium text-ink">Hint</span>
              <input value={hint} onChange={(e) => setHint(e.target.value)} className="rounded-xl border border-border-input bg-white px-4 py-3 text-sm text-ink" />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-2 text-sm">
                <span className="font-medium text-ink">Price</span>
                <input type="number" value={price} onChange={(e) => setPrice(e.target.value)} className="rounded-xl border border-border-input bg-white px-4 py-3 text-sm text-ink" />
              </label>
              <label className="flex flex-col gap-2 text-sm">
                <span className="font-medium text-ink">Stock</span>
                <input type="number" value={stock} onChange={(e) => setStock(e.target.value)} className="rounded-xl border border-border-input bg-white px-4 py-3 text-sm text-ink" />
              </label>
            </div>
          </div>

          <div className="flex flex-col gap-3 rounded-2xl border border-border-card bg-white p-4">
            <span className="text-sm font-semibold text-ink">Linked sports</span>
            <div className="flex flex-wrap gap-2">
              {item.sports.map((sportId) => (
                <span key={sportId} className="rounded-full bg-surface-muted px-3 py-1 text-xs text-slate">{sportId}</span>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <button onClick={save} type="button" className="flex h-12 items-center justify-center rounded-full bg-ink px-5 text-sm font-semibold text-white">
              Save item
            </button>
            <button onClick={remove} type="button" className="flex h-12 items-center justify-center rounded-full border border-negative text-sm font-semibold text-negative">
              Remove item from shop
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
