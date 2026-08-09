import { useState } from 'react'
import { Check, Download, Mail, MessageCircle, RotateCcw } from 'lucide-react'
import { invoiceSummaryText, shortId, type InvoiceData } from '../invoice'
import { downloadInvoicePdf } from '../../lib/invoicePdf'
import { shareOnWhatsApp } from '../../lib/share'
import { useEmailInvoice } from '../../api/hooks'
import { ApiError } from '../../api/client'
import BookingTicket from '../BookingTicket'
import SuccessGraphic from '../../checkin/SuccessGraphic'
import HomeCountdownButton from '../../ui/HomeCountdown'

export default function Confirmation({
  invoice,
  onDone,
  onBookAnother,
}: {
  invoice: InvoiceData
  onDone: () => void
  onBookAnother: () => void
}) {
  const summary = invoiceSummaryText(invoice)

  const emailInvoice = useEmailInvoice()
  // Only shown when there is nothing on file — an address is usually taken during
  // Player Details, and asking again for one we already have wastes the counter's
  // time on a screen the customer is standing at.
  const [address, setAddress] = useState(invoice.customer.email ?? '')
  const [asking, setAsking] = useState(false)
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const send = (to?: string) => {
    if (!invoice.bookingId) return
    setError(null)
    emailInvoice
      .mutateAsync({ bookingId: invoice.bookingId, to })
      .then((result) => {
        setSentTo(result.sent_to)
        setAsking(false)
      })
      .catch((err) => {
        // A missing address comes back as a 409 — that is a prompt, not a failure.
        if (err instanceof ApiError && err.isConflict && !to) {
          setAsking(true)
          return
        }
        setError(
          err instanceof ApiError ? err.message : 'Could not reach the server to send it.',
        )
      })
  }

  const emailLabel = emailInvoice.isPending
    ? 'Sending…'
    : sentTo
      ? `Sent to ${sentTo}`
      : 'Email invoice'

  return (
    <div className="flex w-full max-w-[480px] flex-col items-center gap-[clamp(1.25rem,2.5vw,1.75rem)]">
      <div className="flex flex-col items-center gap-1.5 text-center">
        <SuccessGraphic className="w-full max-w-[140px]" />
        <p className="font-display text-[clamp(1.25rem,2vw,1.5rem)] font-bold text-ink">Booking confirmed</p>
        <p className="text-[clamp(0.9375rem,1.2vw,1.0625rem)] font-semibold text-muted">
          {invoice.sportName} · {invoice.courtName} · {invoice.dateLabel}
          {invoice.timeRange ? `, ${invoice.timeRange}` : ''}
        </p>
        {invoice.bookingId && (
          <span className="mt-1 rounded-full bg-ink px-3.5 py-1 font-mono text-xs font-semibold text-white">
            {invoice.invoiceNo ?? shortId(invoice.bookingId)}
          </span>
        )}
      </div>

      <div id="invoice-print-area" className="w-full">
        <BookingTicket invoice={invoice} />
      </div>

      <div className="grid w-full grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => downloadInvoicePdf(invoice)}
          className="flex items-center justify-center gap-2 rounded-xl bg-surface-muted py-[clamp(0.875rem,1.6vw,1.125rem)] text-[clamp(0.9375rem,1.1vw,1rem)] font-bold text-ink"
        >
          <Download size={17} strokeWidth={2} />
          PDF
        </button>
        <button
          type="button"
          onClick={() => shareOnWhatsApp(summary, invoice.customer.phone)}
          className="flex items-center justify-center gap-2 rounded-xl bg-surface-muted py-[clamp(0.875rem,1.6vw,1.125rem)] text-[clamp(0.9375rem,1.1vw,1rem)] font-bold text-ink"
        >
          <MessageCircle size={17} strokeWidth={2} />
          WhatsApp
        </button>
      </div>

      <div className="flex w-full flex-col gap-2">
        <button
          type="button"
          disabled={!invoice.bookingId || emailInvoice.isPending || sentTo !== null}
          onClick={() => send(invoice.customer.email || undefined)}
          className={`flex w-full items-center justify-center gap-2 rounded-xl py-[clamp(0.875rem,1.6vw,1.125rem)] text-[clamp(0.9375rem,1.1vw,1rem)] font-bold transition-colors disabled:cursor-default ${
            sentTo ? 'bg-lime text-lime-ink' : 'bg-surface-muted text-ink disabled:opacity-60'
          }`}
        >
          {sentTo ? <Check size={17} strokeWidth={2.5} /> : <Mail size={17} strokeWidth={2} />}
          {emailLabel}
        </button>

        {asking && (
          <div className="flex w-full flex-col gap-2 rounded-xl bg-surface-muted p-3">
            <label className="text-[clamp(0.8125rem,1vw,0.875rem)] font-semibold text-ink">
              No email on file — where should this go?
            </label>
            <div className="flex gap-2">
              <input
                type="email"
                inputMode="email"
                autoFocus
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && address.includes('@')) send(address.trim())
                }}
                placeholder="player@example.com"
                className="min-w-0 flex-1 rounded-lg border border-border-input bg-white px-3 py-2.5 text-[clamp(0.875rem,1vw,0.9375rem)] text-ink placeholder:text-muted focus:border-ink focus:outline-none"
              />
              <button
                type="button"
                disabled={!address.includes('@') || emailInvoice.isPending}
                onClick={() => send(address.trim())}
                className="shrink-0 rounded-lg bg-ink px-4 text-[clamp(0.875rem,1vw,0.9375rem)] font-bold text-white disabled:opacity-40"
              >
                Send
              </button>
            </div>
          </div>
        )}

        {error && (
          <p role="alert" className="text-[clamp(0.8125rem,1vw,0.875rem)] font-medium text-negative">
            {error}
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={onBookAnother}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-surface-muted py-[clamp(0.875rem,1.6vw,1.125rem)] text-[clamp(0.9375rem,1.1vw,1rem)] font-bold text-ink"
      >
        <RotateCcw size={17} strokeWidth={2} />
        Book another court
      </button>

      <HomeCountdownButton onHome={onDone} />
    </div>
  )
}
