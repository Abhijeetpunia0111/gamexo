import { CheckCircle2, Search, XCircle } from 'lucide-react'
import { money } from '../../lib/format'
import { timeLabel } from '../../checkin/useCheckIn'
import HomeCountdownButton from '../../ui/HomeCountdown'
import { durationLabel, extraMinutes, type CheckoutBooking } from '../useCheckout'

function Field({ label, value, tone }: { label: string; value: string; tone?: 'due' | 'ok' }) {
  return (
    <div className="flex flex-col">
      <p className="text-[clamp(0.75rem,0.9vw,0.8125rem)] font-medium text-muted">{label}</p>
      <p
        className={`text-[clamp(0.9375rem,1.2vw,1.0625rem)] font-bold ${
          tone === 'due' ? 'text-flame' : tone === 'ok' ? 'text-positive' : 'text-ink'
        }`}
      >
        {value}
      </p>
    </div>
  )
}

function Found({
  booking,
  onSettle,
  onHome,
}: {
  booking: CheckoutBooking
  onSettle: () => void
  onHome: () => void
}) {
  const equipmentCharge = Number(booking.equipment_charge)
  const balanceDue = Number(booking.balance_due)
  const settled = balanceDue <= 0
  const overMinutes = extraMinutes(booking)

  return (
    <div className="flex w-full max-w-[520px] flex-col items-center gap-[clamp(1.25rem,2.5vw,1.75rem)]">
      <div className="flex w-full flex-col gap-[clamp(1rem,2vw,1.375rem)] rounded-2xl border-[3px] border-white bg-white px-[clamp(1.25rem,2.5vw,1.75rem)] py-[clamp(1.25rem,2.5vw,1.75rem)] shadow-[0px_20px_45px_-15px_rgba(0,0,0,0.18)]">
        <div className="flex flex-col gap-1">
          <p className="text-[clamp(0.75rem,0.9vw,0.8125rem)] font-medium text-muted">
            #BK-{booking.id.slice(0, 8).toUpperCase()}
          </p>
          <p className="font-display text-[clamp(1.25rem,2vw,1.5rem)] font-bold text-ink">{booking.customer_name}</p>
          <p className="text-[clamp(0.9375rem,1.2vw,1.0625rem)] font-semibold text-ink">
            {booking.sport_name ?? 'Court'} <span className="font-medium text-muted">· {booking.court_name ?? '—'}</span>
          </p>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-black/10 px-[clamp(1rem,1.8vw,1.375rem)] py-[clamp(0.875rem,1.5vw,1.0625rem)]">
          <Field label="Check-in" value={timeLabel(booking.starts_at)} />
          <Field label="Checkout" value={timeLabel(new Date().toISOString())} />
          <Field label="Duration" value={durationLabel(booking.duration_min)} />
          <Field label="Extra time" value={overMinutes > 0 ? `${overMinutes} min` : 'None'} tone={overMinutes > 0 ? 'due' : undefined} />
          <Field label="Add-ons" value={equipmentCharge > 0 ? money(equipmentCharge) : 'None'} />
          <Field label="Amount due" value={settled ? 'Paid in full' : money(balanceDue)} tone={settled ? 'ok' : 'due'} />
        </div>
      </div>

      {settled ? (
        <div className="flex w-full max-w-[380px] flex-col items-center gap-3">
          <div className="flex items-center gap-2 text-positive">
            <CheckCircle2 size={18} strokeWidth={2} />
            <span className="text-sm font-semibold">Already settled — nothing due</span>
          </div>
          <HomeCountdownButton onHome={onHome} />
        </div>
      ) : (
        <button
          type="button"
          onClick={onSettle}
          className="flex w-full max-w-[380px] items-center justify-center gap-2 rounded-xl bg-ink py-[clamp(0.875rem,1.6vw,1.125rem)] text-[clamp(1rem,1.2vw,1.125rem)] font-bold text-white"
        >
          Settle {money(balanceDue)}
        </button>
      )}
    </div>
  )
}

function NotFound({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex w-full max-w-[420px] flex-col items-center gap-6 text-center">
      <span className="flex size-16 items-center justify-center rounded-full bg-surface-muted text-muted">
        <XCircle size={30} strokeWidth={1.75} />
      </span>
      <div className="flex flex-col gap-2">
        <p className="font-display text-[clamp(1.15rem,1.9vw,1.5rem)] font-bold text-ink">No active session found</p>
        <p className="text-[clamp(0.9375rem,1.1vw,1rem)] text-muted">
          That number isn't checked into a game right now. Double check it and try again.
        </p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-ink py-[clamp(0.875rem,1.6vw,1.125rem)] text-[clamp(1rem,1.2vw,1.125rem)] font-bold text-white"
      >
        Try another number
      </button>
    </div>
  )
}

export default function SessionResult({
  status,
  booking,
  onSettle,
  onRetry,
  onHome,
}: {
  status: 'loading' | 'found' | 'not-found'
  booking?: CheckoutBooking | null
  onSettle: () => void
  onRetry: () => void
  onHome: () => void
}) {
  if (status === 'loading') {
    return (
      <div className="flex flex-col items-center gap-3 text-muted">
        <Search size={28} strokeWidth={1.75} className="animate-pulse" />
        <p className="text-sm">Looking up their session…</p>
      </div>
    )
  }

  if (status === 'found' && booking) {
    return <Found booking={booking} onSettle={onSettle} onHome={onHome} />
  }

  return <NotFound onRetry={onRetry} />
}
