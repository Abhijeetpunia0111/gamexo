import { useState } from 'react'
import { CircleDot, Circle, CalendarCheck2, IndianRupee } from 'lucide-react'
import {
  EQUIPMENT,
  SPORTS,
  balanceOf,
  courtById,
  equipmentForSport,
  extendByHour,
  money,
  priceEquipment,
  sportById,
  withExtras,
  type Booking,
  type Sale,
} from '../data/booking'
import chevronDown from '../assets/figma/chevron-down.svg'
import * as db from '../lib/db'
import { courtOccupancy, canExtend, effectiveState, todayISO } from './derive'
import { useNow } from './useNow'
import Tile from './Tile'
import CourtCard from './CourtCard'
import CourtPanel from './CourtPanel'

type ViewMode = 'courts' | 'customers'
type Filter = 'all' | 'live' | 'upcoming' | 'free'

function saleWithExtras(sale: Sale, add: Record<string, number>): Sale {
  const equipment = { ...sale.equipment }
  for (const [id, qty] of Object.entries(add)) {
    const next = (equipment[id] || 0) + qty
    if (next > 0) equipment[id] = next
    else delete equipment[id]
  }
  const { equipmentTotal, gst, total } = priceEquipment(equipment)
  return { ...sale, equipment, equipmentTotal, gst, total }
}

export default function ActiveGames({ onStartBooking }: { onStartBooking: (courtId: string) => void }) {
  db.useDbVersion()
  const now = useNow(15000)
  const [viewMode, setViewMode] = useState<ViewMode>('courts')
  const [filter, setFilter] = useState<Filter>('all')
  const [sportFilter, setSportFilter] = useState<string | null>(null)
  const [sportMenuOpen, setSportMenuOpen] = useState(false)
  const [selectedBookingId, setSelectedBookingId] = useState<string | null>(null)
  const [selectedSaleId, setSelectedSaleId] = useState<string | null>(null)

  const bookings = db.getBookings()
  const sales = db.getSales()
  const adjustments = db.getStockAdjustments()
  const remainingStock = Object.fromEntries(EQUIPMENT.map((e) => [e.id, e.stock + (adjustments[e.id] || 0)]))

  const occ = courtOccupancy(bookings, now)
  const filteredCourts = occ
    .filter((c) => filter === 'all' || c.state === filter)
    .filter((c) => !sportFilter || c.court.sportId === sportFilter)
  const sportFilterLabel = sportFilter ? sportById(sportFilter)?.name : 'All Sports'

  const courtsInPlay = occ.filter((c) => c.state === 'live').length
  const freeCourts = occ.filter((c) => c.state === 'free').length

  const todaysBookings = bookings
    .filter((b) => b.date === todayISO())
    .sort((a, b) => a.startHour - b.startHour)
  const owingSales = sales.filter((s) => balanceOf(s) > 0)
  const owed =
    bookings.reduce((s, b) => s + balanceOf(b), 0) + sales.reduce((s, sale) => s + balanceOf(sale), 0)

  const selectedBooking = selectedBookingId ? db.getBooking(selectedBookingId) || null : null
  const selectedCourt = selectedBooking ? courtById(selectedBooking.courtId) || null : null
  const selectedSale = selectedSaleId ? sales.find((s) => s.id === selectedSaleId) || null : null

  const issueKitBooking = (booking: Booking, itemId: string) => {
    if ((remainingStock[itemId] ?? 0) <= 0) return
    db.saveBooking(withExtras(booking, { [itemId]: 1 }))
    db.issueStock({ [itemId]: 1 })
  }
  const issueKitSale = (sale: Sale, itemId: string) => {
    if ((remainingStock[itemId] ?? 0) <= 0) return
    db.saveSale(saleWithExtras(sale, { [itemId]: 1 }))
    db.issueStock({ [itemId]: 1 })
  }

  return (
    <div className="flex flex-1 flex-col items-start gap-5 overflow-y-auto px-4 py-5 sm:px-6">
      <p className="w-full text-lg text-ink">Active Courts</p>

      <div className="grid w-full grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <Tile label="Courts In Play" value={String(courtsInPlay)} icon={CircleDot} />
        <Tile label="Free Courts" value={String(freeCourts)} icon={Circle} />
        <Tile label="Bookings Today" value={String(todaysBookings.length)} icon={CalendarCheck2} />
        <Tile label="Amount Owed" value={money(owed)} icon={IndianRupee} alert={owed > 0} />
      </div>

      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <div className="flex rounded-full border border-border-input bg-surface p-1">
          {(['courts', 'customers'] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setViewMode(v)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                viewMode === v ? 'bg-ink text-white' : 'text-slate'
              }`}
            >
              {v === 'courts' ? 'By court' : 'By customer'}
            </button>
          ))}
        </div>

        {viewMode === 'courts' && (
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex flex-wrap gap-2">
              {(
                [
                  ['all', 'All'],
                  ['live', 'In play'],
                  ['free', 'Free'],
                  ['upcoming', 'Next up'],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setFilter(key)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                    filter === key ? 'border-ink bg-ink text-white' : 'border-border-input bg-surface text-slate'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="relative">
              <button
                type="button"
                onClick={() => setSportMenuOpen((v) => !v)}
                className="flex items-center gap-3 rounded-full border border-border-input bg-surface px-4 py-2 shadow-[0px_1px_2px_0px_rgba(82,88,102,0.09)]"
              >
                <span className="text-sm font-medium text-ink">{sportFilterLabel}</span>
                <img src={chevronDown} alt="" className="h-2.5 w-auto shrink-0" />
              </button>

              {sportMenuOpen && (
                <>
                  <button
                    type="button"
                    aria-label="Close filter"
                    onClick={() => setSportMenuOpen(false)}
                    className="fixed inset-0 z-10"
                  />
                  <div className="absolute right-0 z-20 mt-2 w-48 overflow-hidden rounded-lg border border-border-card bg-white py-1 shadow-lg">
                    <button
                      type="button"
                      onClick={() => {
                        setSportFilter(null)
                        setSportMenuOpen(false)
                      }}
                      className={`flex w-full items-center px-3.5 py-2 text-left text-sm ${
                        sportFilter === null ? 'font-semibold text-ink' : 'text-slate hover:bg-surface-muted'
                      }`}
                    >
                      All Sports
                    </button>
                    {SPORTS.map((sport) => (
                      <button
                        key={sport.id}
                        type="button"
                        onClick={() => {
                          setSportFilter(sport.id)
                          setSportMenuOpen(false)
                        }}
                        className={`flex w-full items-center px-3.5 py-2 text-left text-sm ${
                          sportFilter === sport.id ? 'font-semibold text-ink' : 'text-slate hover:bg-surface-muted'
                        }`}
                      >
                        {sport.name}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {viewMode === 'courts' ? (
        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredCourts.map(({ court, state, booking }) => (
            <CourtCard
              key={court.id}
              court={court}
              state={state}
              booking={booking}
              now={now}
              onClick={() => (booking ? setSelectedBookingId(booking.id) : onStartBooking(court.id))}
            />
          ))}
        </div>
      ) : (
        <div className="flex w-full flex-col gap-5">
          <div className="w-full overflow-hidden rounded-xl border border-border-card bg-surface">
            {todaysBookings.map((b) => {
              const st = effectiveState(b, now)
              const court = courtById(b.courtId)!
              const balance = balanceOf(b)
              return (
                <button
                  key={b.id}
                  type="button"
                  onClick={() => setSelectedBookingId(b.id)}
                  className="flex w-full items-center gap-4 border-b border-border-card px-4 py-3 text-left last:border-b-0 hover:bg-surface-muted"
                >
                  <span className="w-16 shrink-0 text-xs font-medium text-slate">
                    {formatClockHour(b.startHour)}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
                    {b.customer.name}
                  </span>
                  <span className="hidden w-28 shrink-0 text-xs text-slate sm:block">{court.name}</span>
                  <span
                    className={`w-16 shrink-0 rounded-full px-2 py-0.5 text-center text-[11px] font-semibold ${
                      st === 'live'
                        ? 'bg-lime text-lime-ink'
                        : st === 'upcoming'
                          ? 'bg-surface-muted text-slate'
                          : 'bg-border-card text-muted'
                    }`}
                  >
                    {st === 'live' ? 'Live' : st === 'upcoming' ? 'Next' : 'Done'}
                  </span>
                  <span className={`w-20 shrink-0 text-right text-xs font-semibold ${balance > 0 ? 'text-negative' : 'text-positive'}`}>
                    {balance > 0 ? money(balance) : 'Paid'}
                  </span>
                </button>
              )
            })}
            {todaysBookings.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-muted">No bookings today yet.</p>
            )}
          </div>

          {owingSales.length > 0 && (
            <div className="flex w-full flex-col gap-3">
              <p className="text-sm font-semibold text-ink">Counter tabs</p>
              <div className="w-full overflow-hidden rounded-xl border border-border-card bg-surface">
                {owingSales.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setSelectedSaleId(s.id)}
                    className="flex w-full items-center gap-4 border-b border-border-card px-4 py-3 text-left last:border-b-0 hover:bg-surface-muted"
                  >
                    <span className="flex-1 text-sm font-medium text-ink">{s.customer.name}</span>
                    <span className="text-xs text-negative font-semibold">{money(balanceOf(s))} due</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {selectedBooking && selectedCourt && (
        <CourtPanel
          subject={{ kind: 'booking', booking: selectedBooking }}
          onClose={() => setSelectedBookingId(null)}
          onIssueKit={(itemId) => issueKitBooking(selectedBooking, itemId)}
          onSettle={(method) =>
            db.saveBooking({
              ...selectedBooking,
              paidTotal: selectedBooking.total,
              payment: { method, status: 'paid' },
            })
          }
          onCheckIn={() => db.saveBooking({ ...selectedBooking, status: 'checked-in' })}
          onFinish={() => db.saveBooking({ ...selectedBooking, status: 'completed' })}
          onExtend={() => db.saveBooking(extendByHour(selectedBooking))}
          canExtend={canExtend(selectedBooking, bookings)}
          kitOptions={equipmentForSport(selectedCourt.sportId)}
          remainingStock={remainingStock}
        />
      )}

      {selectedSale && (
        <CourtPanel
          subject={{ kind: 'tab', sale: selectedSale }}
          onClose={() => setSelectedSaleId(null)}
          onIssueKit={(itemId) => issueKitSale(selectedSale, itemId)}
          onSettle={(method) =>
            db.saveSale({ ...selectedSale, paidTotal: selectedSale.total, payment: { method, status: 'paid' } })
          }
          onCheckIn={() => {}}
          onFinish={() => {}}
          onExtend={() => {}}
          canExtend={false}
          kitOptions={EQUIPMENT.filter((e) => e.sports.length === 0)}
          remainingStock={remainingStock}
        />
      )}
    </div>
  )
}

function formatClockHour(startHour: number) {
  const h = Math.floor(startHour)
  const m = Math.round((startHour - h) * 60)
  const d = new Date()
  d.setHours(h, m, 0, 0)
  return d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })
}
