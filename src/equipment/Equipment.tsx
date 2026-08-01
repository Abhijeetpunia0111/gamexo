import { useState } from 'react'
import { Package } from 'lucide-react'
import { EQUIPMENT, money, type Equipment as EquipmentItem } from '../data/booking'
import * as db from '../lib/db'
import IssueDialog from './IssueDialog'

function stats(item: EquipmentItem, adjustments: Record<string, number>) {
  const available = item.stock + (adjustments[item.id] || 0)
  const rentals = db.getRentals().filter((r) => r.itemId === item.id)
  const issued = rentals.filter((r) => r.status === 'out').reduce((sum, r) => sum + r.qty, 0)
  const lost = rentals.filter((r) => r.status === 'lost').reduce((sum, r) => sum + r.qty, 0)
  const maintenance = rentals.filter((r) => r.status === 'maintenance').reduce((sum, r) => sum + r.qty, 0)
  return { available, issued, lost, maintenance }
}

export default function Equipment() {
  db.useDbVersion()
  const [issuing, setIssuing] = useState<EquipmentItem | null>(null)
  const adjustments = db.getStockAdjustments()
  const openRentals = db.getRentals().filter((r) => r.status === 'out' || r.status === 'maintenance')

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-4 py-5 sm:px-6">
      <p className="text-lg text-ink">Inventory</p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {EQUIPMENT.map((item) => {
          const s = stats(item, adjustments)
          return (
            <div key={item.id} className="flex flex-col gap-3 rounded-xl border border-border-card bg-white p-4">
              <div className="flex items-center gap-3">
                <div className="flex size-9 items-center justify-center rounded-full bg-surface-muted text-ink">
                  <Package size={16} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-ink">{item.name}</p>
                  <p className="text-xs text-muted">{item.hint}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <Stat label="On shelf" value={String(item.stock)} />
                <Stat label="Available" value={String(s.available)} tone={s.available <= 0 ? 'negative' : undefined} />
                {item.returnable && <Stat label="Issued" value={String(s.issued)} />}
                {item.returnable && s.lost > 0 && <Stat label="Lost" value={String(s.lost)} tone="negative" />}
                {item.returnable && s.maintenance > 0 && <Stat label="Maintenance" value={String(s.maintenance)} tone="flame" />}
              </div>

              <div className="flex items-center justify-between border-t border-border-card pt-3">
                <span className="text-sm font-medium text-positive">{money(item.price)}</span>
                {item.returnable ? (
                  <button
                    type="button"
                    disabled={s.available <= 0}
                    onClick={() => setIssuing(item)}
                    className="rounded-lg border border-border-input bg-white px-3.5 py-1.5 text-xs text-ink disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Issue
                  </button>
                ) : (
                  <span className="text-xs text-muted">Sold via Add-ons</span>
                )}
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
                    <td className="px-4 py-3 text-slate">{new Date(r.dueBackAt).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${r.status === 'maintenance' ? 'bg-flame/15 text-flame' : 'bg-surface-muted text-ink'}`}>
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
                    Nothing checked out right now.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {issuing && <IssueDialog item={issuing} onClose={() => setIssuing(null)} />}
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
