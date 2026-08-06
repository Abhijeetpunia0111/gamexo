import { Download, Mail, MessageCircle, RotateCcw } from 'lucide-react'
import { invoiceSummaryText, shortId, type InvoiceData } from '../invoice'
import { downloadInvoicePdf } from '../../lib/invoicePdf'
import { shareByEmail, shareOnWhatsApp } from '../../lib/share'
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

      <button
        type="button"
        onClick={() => shareByEmail(`Invoice — ${invoice.facility.name}`, summary, invoice.customer.email)}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-surface-muted py-[clamp(0.875rem,1.6vw,1.125rem)] text-[clamp(0.9375rem,1.1vw,1rem)] font-bold text-ink"
      >
        <Mail size={17} strokeWidth={2} />
        Email invoice
      </button>

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
