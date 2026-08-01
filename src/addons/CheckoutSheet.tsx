import { useEffect, useState } from 'react'
import { Check, Search, X } from 'lucide-react'
import { balanceOf, courtById, money, priceEquipment, withExtras, type Booking } from '../data/booking'
import * as db from '../lib/db'

const inputClass =
  'w-full rounded-lg border border-border-input bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-muted focus:border-ink focus:outline-none'

type Mode = 'booking' | 'new'

export default function CheckoutSheet({
  tray,
  onClose,
  onDone,
}: {
  tray: Record<string, number>
  onClose: () => void
  onDone: () => void
}) {
  db.useDbVersion()
  const [mode, setMode] = useState<Mode>('booking')
  const [query, setQuery] = useState('')
  const [pickedId, setPickedId] = useState<string | null>(null)

  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [payingNow, setPayingNow] = useState(true)

  const [success, setSuccess] = useState<{ headline: string; detail: string } | null>(null)

  const totals = priceEquipment(tray)

  const openGames = db
    .getBookings()
    .filter((b) => b.status !== 'completed')
    .filter((b) => {
      const q = query.trim().toLowerCase()
      if (!q) return true
      const court = courtById(b.courtId)
      return b.customer.name.toLowerCase().includes(q) || b.customer.phone.includes(q) || court?.name.toLowerCase().includes(q)
    })
    .slice(0, 6)

  const picked = openGames.find((b) => b.id === pickedId) || db.getBooking(pickedId || '')

  const attach = () => {
    if (!picked) return
    const updated = withExtras(picked, tray)
    db.saveBooking(updated)
    db.issueStock(tray)
    setSuccess({
      headline: `Added to ${courtById(updated.courtId)?.name}`,
      detail: `${updated.customer.name} · balance now ${money(balanceOf(updated))}`,
    })
  }

  const phoneOk = /^\d{10}$/.test(phone)
  const existing = phoneOk ? db.findCustomer(phone) : undefined

  // A phone number we've seen before fills in the name — nothing typed twice.
  useEffect(() => {
    if (!phoneOk) return
    const match = db.findCustomer(phone)
    if (match) setName(match.name)
  }, [phone, phoneOk])

  const openTab = () => {
    if (!phoneOk || !name.trim()) return
    const id = `CS${Math.floor(10000 + Math.random() * 89999)}`
    const sale = {
      id,
      customer: { name: name.trim(), phone, email: existing?.email || '' },
      equipment: tray,
      equipmentTotal: totals.equipmentTotal,
      gst: totals.gst,
      total: totals.total,
      paidTotal: payingNow ? totals.total : 0,
      payment: payingNow ? { method: 'upi', status: 'paid' } : null,
      createdAt: new Date().toISOString(),
    }
    db.saveSale(sale)
    db.upsertCustomer({ name: sale.customer.name, phone: sale.customer.phone, email: sale.customer.email })
    db.issueStock(tray)
    setSuccess({
      headline: 'Tab opened',
      detail: payingNow ? 'Paid in full.' : `Balance to collect: ${money(totals.total)}`,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 sm:items-center" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[85vh] w-full flex-col gap-5 overflow-y-auto rounded-t-2xl bg-white p-6 sm:max-w-[480px] sm:rounded-2xl"
      >
        {success ? (
          <div className="flex flex-col items-center gap-4 py-6 text-center">
            <div className="flex size-14 items-center justify-center rounded-full bg-lime">
              <Check size={24} className="text-lime-ink" />
            </div>
            <div>
              <p className="text-lg font-semibold text-ink">{success.headline}</p>
              <p className="mt-1 text-sm text-slate">{success.detail}</p>
            </div>
            <button
              type="button"
              onClick={onDone}
              className="flex h-11 items-center justify-center rounded-full px-8 text-sm text-[#fefefe]"
              style={{ backgroundImage: 'linear-gradient(105deg, rgb(41,41,41) 2%, rgb(26,26,26) 100%)' }}
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <p className="text-lg font-semibold text-ink">Checkout</p>
              <button type="button" onClick={onClose} aria-label="Close" className="text-muted hover:text-ink">
                <X size={20} />
              </button>
            </div>

            <p className="text-sm text-slate">There is no anonymous sale — every tray lands on a bill or a tab.</p>

            <div className="flex items-center gap-1 rounded-lg bg-surface-muted p-1">
              <button
                type="button"
                onClick={() => setMode('booking')}
                className={`flex-1 rounded-md py-2 text-sm transition-colors ${mode === 'booking' ? 'bg-white text-ink shadow-sm' : 'text-slate'}`}
              >
                A game in play
              </button>
              <button
                type="button"
                onClick={() => setMode('new')}
                className={`flex-1 rounded-md py-2 text-sm transition-colors ${mode === 'new' ? 'bg-white text-ink shadow-sm' : 'text-slate'}`}
              >
                New customer
              </button>
            </div>

            {mode === 'booking' ? (
              <div className="flex flex-col gap-3">
                <div className="relative">
                  <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
                  <input
                    className={`${inputClass} pl-9`}
                    placeholder="Search name, phone or court"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>

                <div className="flex flex-col gap-2">
                  {openGames.length === 0 && <p className="py-4 text-center text-sm text-muted">No open games match.</p>}
                  {openGames.map((b) => (
                    <BookingRow key={b.id} booking={b} active={pickedId === b.id} onClick={() => setPickedId(b.id)} />
                  ))}
                </div>

                <button
                  type="button"
                  disabled={!picked}
                  onClick={attach}
                  className="flex h-11 w-full items-center justify-center rounded-full text-sm text-[#fefefe] disabled:opacity-40"
                  style={{ backgroundImage: 'linear-gradient(105deg, rgb(41,41,41) 2%, rgb(26,26,26) 100%)' }}
                >
                  Add {money(totals.total)} to their bill
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-sm font-medium text-slate">Phone number</span>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-muted">+91</span>
                    <input
                      className={`${inputClass} pl-11`}
                      inputMode="numeric"
                      maxLength={10}
                      placeholder="90000 00000"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
                    />
                  </div>
                  {existing && <span className="text-xs text-positive">Welcome back, {existing.name.split(' ')[0]}.</span>}
                </label>

                <label className="flex flex-col gap-1.5">
                  <span className="text-sm font-medium text-slate">Name</span>
                  <input
                    className={inputClass}
                    placeholder="Customer's name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>

                <label className="flex items-center gap-2 text-sm text-ink">
                  <input type="checkbox" checked={payingNow} onChange={(e) => setPayingNow(e.target.checked)} className="size-4 accent-black" />
                  Paying right now
                </label>

                <div className="flex items-center justify-between border-t border-border-card pt-3 text-sm">
                  <span className="text-slate">Total</span>
                  <span className="font-semibold text-ink">{money(totals.total)}</span>
                </div>

                <button
                  type="button"
                  disabled={!phoneOk || !(name.trim() || existing)}
                  onClick={openTab}
                  className="flex h-11 w-full items-center justify-center rounded-full text-sm text-[#fefefe] disabled:opacity-40"
                  style={{ backgroundImage: 'linear-gradient(105deg, rgb(41,41,41) 2%, rgb(26,26,26) 100%)' }}
                >
                  {payingNow ? `Charge ${money(totals.total)}` : 'Open tab'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function BookingRow({ booking, active, onClick }: { booking: Booking; active: boolean; onClick: () => void }) {
  const court = courtById(booking.courtId)
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center justify-between rounded-lg border px-3.5 py-2.5 text-left transition-colors ${
        active ? 'border-ink bg-surface-muted' : 'border-border-card bg-white hover:border-ink/30'
      }`}
    >
      <div>
        <p className="text-sm font-medium text-ink">{booking.customer.name}</p>
        <p className="text-xs text-muted">
          {court?.name} · {booking.customer.phone}
        </p>
      </div>
      {active && <Check size={16} className="text-ink" />}
    </button>
  )
}
