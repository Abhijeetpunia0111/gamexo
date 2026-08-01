import { Edit3, Minus, Package, Plus, Trash2 } from 'lucide-react'
import { EQUIPMENT, SPORTS, listEquipment, money, type Equipment as EquipmentItem } from '../data/booking'
import { useState } from 'react'
import * as db from '../lib/db'
import EquipmentEditorDrawer from './EquipmentEditorDrawer'

function fallbackFor(item: EquipmentItem & { activeForSale: boolean }) {
  return { stock: item.stock, activeForSale: item.activeForSale, sports: item.sports }
}

function stats(itemId: string, adjustments: Record<string, number>, stock: number) {
  const available = stock + (adjustments[itemId] || 0)
  const rentals = db.getRentals().filter((r) => r.itemId === itemId)
  const issued = rentals.filter((r) => r.status === 'out').reduce((sum, r) => sum + r.qty, 0)
  const lost = rentals.filter((r) => r.status === 'lost').reduce((sum, r) => sum + r.qty, 0)
  const maintenance = rentals.filter((r) => r.status === 'maintenance').reduce((sum, r) => sum + r.qty, 0)
  return { available, issued, lost, maintenance }
}

export default function Equipment() {
  db.useDbVersion()
  const adjustments = db.getStockAdjustments()
  const items = listEquipment()
  const openRentals = db.getRentals().filter((r) => r.status === 'out' || r.status === 'maintenance')
  const [editorItem, setEditorItem] = useState<(EquipmentItem & { activeForSale: boolean }) | null>(null)

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-4 py-5 sm:px-6">
      <div>
        <p className="text-lg text-ink">Inventory</p>
        <p className="text-sm text-muted">
          Restock, link kit to a sport for relevant booking recommendations, and control what shows up in the shop.
          Issuing and returning gear happens from Add-ons.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => {
          const s = stats(item.id, adjustments, item.stock)
          const fallback = fallbackFor(item)
          return (
            <div key={item.id} className={`flex flex-col gap-3 rounded-3xl border bg-white p-4 ${item.activeForSale ? 'border-border-card' : 'border-border-card opacity-60'}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-3">
                  <div className="flex size-9 items-center justify-center rounded-full bg-surface-muted text-ink">
                    <Package size={16} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-ink">{item.name}</p>
                    <p className="text-xs text-muted">{item.hint}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setEditorItem(item)}
                    className="flex h-9 w-9 items-center justify-center rounded-full border border-border-input bg-white text-slate shadow-sm transition hover:bg-surface"
                    title="Edit item"
                  >
                    <Edit3 size={16} />
                  </button>
                  <button
                    type="button"
                    onClick={() => db.setEquipmentActive(item.id, !item.activeForSale, fallback)}
                    aria-pressed={item.activeForSale}
                    className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${item.activeForSale ? 'bg-lime' : 'bg-surface-muted'}`}
                    title={item.activeForSale ? 'In shop — tap to hide' : 'Hidden — tap to list in shop'}
                  >
                    <span
                      className={`absolute top-0.5 size-4 rounded-full bg-white shadow transition-transform ${item.activeForSale ? 'translate-x-[18px]' : 'translate-x-0.5'}`}
                    />
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-lg bg-surface-muted px-3 py-2">
                <span className="text-xs text-muted">On shelf</span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => db.setEquipmentStock(item.id, item.stock - 1, fallback)}
                    className="flex size-6 items-center justify-center rounded-md bg-white text-ink"
                  >
                    <Minus size={12} />
                  </button>
                  <span className="w-6 text-center text-sm font-semibold text-ink">{item.stock}</span>
                  <button
                    type="button"
                    onClick={() => db.setEquipmentStock(item.id, item.stock + 1, fallback)}
                    className="flex size-6 items-center justify-center rounded-md bg-white text-ink"
                  >
                    <Plus size={12} />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <Stat label="Available" value={String(s.available)} tone={s.available <= 0 ? 'negative' : undefined} />
                {item.returnable && <Stat label="Issued" value={String(s.issued)} />}
                {item.returnable && s.lost > 0 && <Stat label="Lost" value={String(s.lost)} tone="negative" />}
                {item.returnable && s.maintenance > 0 && <Stat label="Maintenance" value={String(s.maintenance)} tone="flame" />}
              </div>

              <div className="flex flex-col gap-1.5 border-t border-border-card pt-3">
                <span className="text-xs font-medium text-muted">Linked sports · blank = general kit</span>
                <div className="flex flex-wrap gap-1.5">
                  {SPORTS.map((sport) => {
                    const linked = item.sports.includes(sport.id)
                    return (
                      <button
                        key={sport.id}
                        type="button"
                        onClick={() => {
                          const next = linked ? item.sports.filter((id) => id !== sport.id) : [...item.sports, sport.id]
                          db.setEquipmentSports(item.id, next, fallback)
                        }}
                        className={`rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                          linked ? 'bg-ink text-bone' : 'bg-surface-muted text-slate'
                        }`}
                      >
                        {sport.name}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-border-card pt-3">
                <span className="text-sm font-medium text-positive">{money(item.price)}</span>
                <span className="text-xs text-muted">{item.returnable ? `₹${item.deposit || 0} deposit` : 'Consumable'}</span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex flex-col gap-3">
        <p className="text-sm font-semibold text-ink">Currently out</p>
        <div className="overflow-hidden rounded-xl border border-border-card bg-white">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-card text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-3 font-medium">Item</th>
                <th className="px-4 py-3 font-medium">Customer</th>
                <th className="px-4 py-3 font-medium">Qty</th>
                <th className="px-4 py-3 font-medium">Due back</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {openRentals.map((r) => {
                const item = EQUIPMENT.find((e) => e.id === r.itemId)
                return (
                  <tr key={r.id} className="border-b border-border-card last:border-0">
                    <td className="px-4 py-3 text-ink">{item?.name}</td>
                    <td className="px-4 py-3 text-slate">
                      {r.customer.name} · {r.customer.phone}
                    </td>
                    <td className="px-4 py-3 text-slate">{r.qty}</td>
                    <td className="px-4 py-3 text-slate">
                      {new Date(r.dueBackAt).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${r.status === 'maintenance' ? 'bg-flame/15 text-flame' : 'bg-surface-muted text-ink'}`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {r.status === 'out' ? (
                        <div className="flex gap-1.5">
                          <button type="button" onClick={() => db.returnRental(r.id, 'ok')} className="rounded-md bg-positive/15 px-2.5 py-1 text-xs font-medium text-positive">
                            Returned
                          </button>
                          <button type="button" onClick={() => db.returnRental(r.id, 'maintenance')} className="rounded-md bg-flame/15 px-2.5 py-1 text-xs font-medium text-flame">
                            Maintenance
                          </button>
                          <button type="button" onClick={() => db.returnRental(r.id, 'lost')} className="rounded-md bg-negative/15 px-2.5 py-1 text-xs font-medium text-negative">
                            Lost
                          </button>
                        </div>
                      ) : (
                        <button type="button" onClick={() => db.resolveMaintenance(r.id)} className="rounded-md bg-positive/15 px-2.5 py-1 text-xs font-medium text-positive">
                          Mark fixed
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
              {openRentals.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-muted">
                    Nothing checked out right now. Gear is issued from Add-ons at checkout.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'negative' | 'flame' }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg bg-surface-muted px-2.5 py-2">
      <span className="text-muted">{label}</span>
      <span className={`font-semibold ${tone === 'negative' ? 'text-negative' : tone === 'flame' ? 'text-flame' : 'text-ink'}`}>{value}</span>
    </div>
  )
}
