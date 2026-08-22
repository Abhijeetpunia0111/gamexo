import { useEffect } from 'react'
import Keyboard from '../../ui/Keyboard'
import arrowRight from '../../assets/figma/checkin/arrow-right-check.svg'

/**
 * Check-in by the code on the customer's ticket.
 *
 * Replaced entry by phone number, which cost four steps and an SMS round trip to
 * establish something the customer was already holding in their hand. The reference
 * is proof enough: it was sent to them privately, and the worst outcome of a wrong
 * guess is checking in to a court someone else paid for — not taking money.
 *
 * The server normalises what is typed, so `XC-B-0042`, `XCB0042`, `B-42` and `42`
 * all resolve to the same booking. That is why this box does not validate a format
 * or force a prefix: the customer keys what they can see, and being strict here
 * would reject inputs the API is perfectly happy with.
 */

// Long enough for a prefix and a five-figure counter, short enough that a phone
// number typed out of habit does not silently fill the field.
const MAX_LEN = 16

export default function EnterBookingId({
  bookingId,
  setBookingId,
  error,
  searching,
  onSubmit,
}: {
  bookingId: string
  setBookingId: (v: string) => void
  error: string | null
  searching: boolean
  onSubmit: () => void
}) {
  const value = bookingId.trim()
  // Needs at least one digit — the counter is the part that identifies the booking,
  // and "XC-B-" alone is just the prefix printed above the screen.
  const ready = /[0-9]/.test(value) && !searching

  const addChar = (ch: string) =>
    setBookingId(bookingId.length < MAX_LEN ? bookingId + ch : bookingId)
  const backspace = () => setBookingId(bookingId.slice(0, -1))

  // A physical keyboard is what the counter tablet gets during development and what
  // a desk with a USB keyboard will use; the on-screen board is for the kiosk.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.length === 1 && /^[A-Za-z0-9 -]$/.test(e.key)) addChar(e.key.toUpperCase())
      else if (e.key === 'Backspace') backspace()
      else if (e.key === 'Enter' && ready) onSubmit()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className="flex w-full max-w-[560px] flex-col items-center gap-[clamp(1.5rem,4vw,2.75rem)]">
      <div className="flex w-full flex-col items-start gap-3">
        <p className="text-[clamp(0.9375rem,1.1vw,1rem)] font-medium text-ink">Enter your Booking ID</p>

        <div
          className={`flex w-full items-center overflow-hidden rounded-xl border-2 bg-border-input px-[clamp(0.9rem,1.6vw,1.0625rem)] py-[clamp(0.9rem,1.8vw,1.5rem)] shadow-[0px_12px_17px_-9px_rgba(0,0,0,0.12)] ${
            error ? 'border-negative' : 'border-white'
          }`}
        >
          <span className="truncate font-mono text-[clamp(1.1rem,1.7vw,1.375rem)] font-semibold tracking-[0.12em] text-ink uppercase">
            {bookingId || <span className="font-sans tracking-normal text-muted">XC-B-0042</span>}
          </span>
        </div>

        {/* One line, never both: an error replaces the hint rather than stacking
            under it, so the layout does not jump on a failed lookup. */}
        {error ? (
          <p role="alert" className="text-[clamp(0.8125rem,1vw,0.875rem)] font-medium text-negative">
            {error}
          </p>
        ) : (
          <p className="text-[clamp(0.8125rem,1vw,0.875rem)] text-muted">
            It's on your booking confirmation — the email or the receipt.
          </p>
        )}
      </div>

      <div className="flex w-full flex-col items-center gap-[clamp(1.25rem,2.6vw,2.1875rem)]">
        <Keyboard
          onChar={addChar}
          onSpace={() => addChar('-')}
          spaceLabel="–"
          onBackspace={backspace}
        />

        <button
          type="button"
          disabled={!ready}
          onClick={onSubmit}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-ink py-[clamp(0.875rem,1.6vw,1.125rem)] text-[clamp(1rem,1.2vw,1.125rem)] font-bold text-white transition-opacity disabled:opacity-40"
        >
          {searching ? 'Checking…' : 'Find my Booking'}
          {!searching && <img src={arrowRight} alt="" className="size-[clamp(1.1rem,1.4vw,1.5rem)]" />}
        </button>
      </div>
    </div>
  )
}
