import { useEffect, useMemo, useState } from 'react'
import { BadgeCheck, CalendarDays, CircleDollarSign, UserRound } from 'lucide-react'
import { balanceOf, courtById, money, sportById, toISO, type Booking } from '../data/booking'
import * as db from '../lib/db'

const statusTone = (payment: Booking['payment']) => {
  const status = payment?.status || 'due'
  if (status === 'paid') return 'bg-lime/20 text-lime-ink'
  return 'bg-amber-50 text-amber-700'
}

const rowAccent = (selected: boolean) => {
  if (selected) return 'bg-surface-muted shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]'
  return 'bg-white hover:bg-surface-muted/70'
}

const paymentLabel = (booking: Booking) => {
  if (booking.payment?.status === 'paid') return 'Paid'
  if (balanceOf(booking) > 0) return 'Due'
  return 'Settled'
}

const formatDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

export default function BookingsPage() {
  const dbVersion = db.useDbVersion()
  const today = toISO(new Date())
  const [startDate, setStartDate] = useState(today)
  const [endDate, setEndDate] = useState(today)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const bookings = useMemo(() => {
    return [...db.getBookings()].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  }, [dbVersion])

  const visibleBookings = useMemo(() => {
    const start = startDate || today
    const end = endDate || today
    const lower = start <= end ? start : end
    const upper = start <= end ? end : start
    return bookings.filter((booking) => booking.date >= lower && booking.date <= upper)
  }, [bookings, endDate, startDate, today])

  useEffect(() => {
    if (visibleBookings.length === 0) {
      setSelectedId(null)
      return
    }
    if (!selectedId || !visibleBookings.some((booking) => booking.id === selectedId)) {
      setSelectedId(visibleBookings[0].id)
    }
  }, [selectedId, visibleBookings])

  const selectedBooking = visibleBookings.find((booking) => booking.id === selectedId) || null

  const previousBookings = useMemo(() => {
    if (!selectedBooking) return []
    return bookings
      .filter((booking) => booking.customer.phone === selectedBooking.customer.phone && booking.id !== selectedBooking.id)
      .slice(0, 5)
  }, [bookings, selectedBooking])

  const customerProfile = selectedBooking ? db.findCustomer(selectedBooking.customer.phone) : undefined
  const membershipStatus = customerProfile && customerProfile.visits >= 8 ? 'Platinum' : customerProfile && customerProfile.visits >= 4 ? 'Gold' : customerProfile && customerProfile.visits >= 2 ? 'Silver' : 'Basic'
  const outstanding = selectedBooking ? balanceOf(selectedBooking) : 0

  const settleDue = () => {
    if (!selectedBooking) return
    db.saveBooking({
      ...selectedBooking,
      paidTotal: selectedBooking.total,
      payment: { method: selectedBooking.payment?.method || 'wallet', status: 'paid' },
    })
  }

  return (
    <div className="flex flex-1 flex-col gap-5 overflow-y-auto bg-page px-4 py-5 sm:px-6">
      <div className="rounded-2xl border border-border-card bg-white p-5 shadow-[0px_5px_13px_0px_rgba(0,0,0,0.05)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xl font-semibold text-ink">Bookings</p>
            <p className="text-sm text-slate">Review every booking in a date range, then open the full customer profile.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="flex items-center gap-2 rounded-lg border border-border-card bg-surface px-3 py-2 text-sm text-slate">
              <CalendarDays size={16} />
              <span>From</span>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="rounded-md border-none bg-transparent text-sm text-ink" />
            </label>
            <label className="flex items-center gap-2 rounded-lg border border-border-card bg-surface px-3 py-2 text-sm text-slate">
              <CalendarDays size={16} />
              <span>To</span>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="rounded-md border-none bg-transparent text-sm text-ink" />
            </label>
          </div>
        </div>
      </div>

      <div className="grid flex-1 gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="flex flex-col gap-3 rounded-2xl border border-border-card bg-white p-4 shadow-[0px_5px_13px_0px_rgba(0,0,0,0.05)]">
          <div className="flex items-center justify-between rounded-xl bg-surface-muted px-3 py-2">
            <div>
              <p className="text-sm font-semibold text-ink">Bookings in range</p>
              <p className="text-xs text-muted">Live list of all confirmed and due bookings</p>
            </div>
            <p className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-slate">{visibleBookings.length} results</p>
          </div>

          {visibleBookings.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border-card px-4 py-8 text-center text-sm text-muted">
              No bookings match the selected dates.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full overflow-hidden rounded-xl text-left text-sm">
                <thead className="border-b border-border-card bg-surface-muted text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-3 py-3">UID</th>
                    <th className="px-3 py-3">Name</th>
                    <th className="px-3 py-3">Game & Court</th>
                    <th className="px-3 py-3">Time</th>
                    <th className="px-3 py-3">Payment</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleBookings.map((booking) => {
                    const court = courtById(booking.courtId)
                    return (
                      <tr key={booking.id} className={`border-b border-border-card/80 last:border-none transition-colors ${rowAccent(selectedId === booking.id)}`}>
                        <td className="px-3 py-3">
                          <button type="button" className="text-left font-semibold text-ink" onClick={() => setSelectedId(booking.id)}>
                            {booking.id}
                          </button>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-col">
                            <span className="font-semibold text-ink">{booking.customer.name}</span>
                            <span className="text-xs text-muted">{booking.customer.phone}</span>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-col">
                            <span className="font-semibold text-ink">{sportById(booking.sportId)?.name || booking.sportId}</span>
                            <span className="text-xs text-muted">{court?.name || booking.courtId}</span>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-col">
                            <span className="font-semibold text-ink">{formatDate(booking.date)}</span>
                            <span className="text-xs text-muted">{booking.startHour}:00 · {booking.hours}h</span>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusTone(booking.payment)}`}>
                            {paymentLabel(booking)}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4 rounded-2xl border border-border-card bg-white p-5 shadow-[0px_5px_13px_0px_rgba(0,0,0,0.05)]">
          {selectedBooking ? (
            <>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-ink">{selectedBooking.customer.name}</p>
                  <p className="text-sm text-slate">{selectedBooking.customer.phone} · {selectedBooking.customer.email || 'No email on file'}</p>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusTone(selectedBooking.payment)}`}>
                  {paymentLabel(selectedBooking)}
                </span>
              </div>

              <div className="grid gap-3 rounded-xl bg-surface-muted p-4 sm:grid-cols-2">
                <div className="flex items-start gap-2">
                  <UserRound size={18} className="mt-0.5 text-ink" />
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Customer</p>
                    <p className="text-sm font-medium text-ink">{selectedBooking.customer.players || '1'} player(s)</p>
                    <p className="text-xs text-slate">{selectedBooking.customer.notes || 'No notes'}</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <CircleDollarSign size={18} className="mt-0.5 text-ink" />
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Due payment</p>
                    <p className="text-sm font-semibold text-ink">{money(outstanding)}</p>
                    <p className="text-xs text-slate">{selectedBooking.payment?.status === 'paid' ? 'Settled in full' : 'Balance can be settled from the counter'}</p>
                  </div>
                </div>
              </div>

              {outstanding > 0 && (
                <button type="button" onClick={settleDue} className="flex h-11 items-center justify-center rounded-full bg-ink px-4 text-sm font-medium text-bone shadow-[0px_4px_10px_0px_rgba(0,0,0,0.08)]">
                  Settle due balance
                </button>
              )}

              <div className="flex flex-col gap-3 rounded-xl border border-border-card bg-surface-muted/50 p-4">
                <div className="flex items-center gap-2">
                  <BadgeCheck size={18} className="text-ink" />
                  <p className="text-sm font-semibold text-ink">Membership</p>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate">Status</span>
                  <span className="font-semibold text-ink">{membershipStatus}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate">Visits</span>
                  <span className="font-semibold text-ink">{customerProfile?.visits || 1}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate">Member since</span>
                  <span className="font-semibold text-ink">{formatDate(selectedBooking.date)}</span>
                </div>
                <div className="rounded-lg bg-surface px-3 py-2 text-sm text-slate">
                  {membershipStatus === 'Platinum' ? 'Priority access, free locker usage, and loyalty perks.' : membershipStatus === 'Gold' ? 'Priority booking slots and member-only offers.' : membershipStatus === 'Silver' ? 'Early access to weekend slots.' : 'Standard access with pay-as-you-go pricing.'}
                </div>
              </div>

              <div className="flex flex-col gap-3">
                <p className="text-sm font-semibold text-ink">Previous bookings</p>
                {previousBookings.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-border-card px-3 py-4 text-sm text-muted">No prior bookings yet.</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {previousBookings.map((booking) => (
                      <div key={booking.id} className="rounded-lg border border-border-card bg-white px-3 py-3 text-sm">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium text-ink">{booking.id}</span>
                          <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${statusTone(booking.payment)}`}>
                            {paymentLabel(booking)}
                          </span>
                        </div>
                        <p className="mt-1 text-slate">{formatDate(booking.date)} · {courtById(booking.courtId)?.name || booking.courtId}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="rounded-xl border border-dashed border-border-card px-4 py-10 text-center text-sm text-muted">
              Select a booking to view the customer profile.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
