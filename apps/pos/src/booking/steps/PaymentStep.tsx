import { Banknote, Building2, CreditCard, QrCode, Receipt } from 'lucide-react'
import { useCourts, useQuote, useSports } from '../../api/hooks'
import { money, startsAtISO } from '../../lib/format'
import { PAYMENT_METHODS, type PaymentMethodId } from '../../lib/paymentMethods'
import { buildProvisionalInvoice } from '../invoice'
import { traySelections } from '../offers'
import { downloadInvoicePdf } from '../../lib/invoicePdf'
import InvoiceDocument from '../InvoiceDocument'
import type { Draft } from '../types'
import arrowRight from '../../assets/figma/checkin/arrow-right-check.svg'

const METHOD_ICONS: Record<PaymentMethodId, typeof QrCode> = {
  upi: QrCode,
  card: CreditCard,
  cash: Banknote,
  bank: Building2,
  cheque: Receipt,
}

export default function PaymentStep({
  draft,
  setDraft,
  processing,
  onPay,
  onEditStep,
}: {
  draft: Draft
  setDraft: (patch: Partial<Draft>) => void
  processing: boolean
  onPay: () => void
  onEditStep: (step: number) => void
}) {
  const sportsQuery = useSports()
  const courtsQuery = useCourts(draft.sportId || undefined)
  const sport = sportsQuery.data?.find((s) => s.id === draft.sportId)
  const court = courtsQuery.data?.find((c) => c.id === draft.courtId)

  const startsAt = draft.date && draft.startHour != null ? startsAtISO(draft.date, draft.startHour) : null
  const equipment = traySelections(draft.equipment)
  const quoteQuery = useQuote(
    court && startsAt ? { courtId: court.id, startsAt, durationMin: draft.hours * 60, equipment } : null,
  )

  const invoice = buildProvisionalInvoice(draft, sport, court, quoteQuery.data)
  const pricingReady = !quoteQuery.isPending && !quoteQuery.error

  return (
    <div className="flex w-full flex-col gap-5 lg:flex-row lg:items-start">
      <div className="min-w-0 flex-1">
        {quoteQuery.error && (
          <p role="alert" className="mb-3 text-sm text-negative">
            Could not price this booking: {quoteQuery.error instanceof Error ? quoteQuery.error.message : 'unknown error'}
          </p>
        )}
        <InvoiceDocument invoice={invoice} onDownloadPdf={() => downloadInvoicePdf(invoice)} />
      </div>

      <div className="flex w-full flex-col gap-4 lg:w-[380px] lg:shrink-0">
        <div className="flex w-full flex-col gap-3 rounded-2xl bg-surface p-[clamp(1rem,1.8vw,1.25rem)]">
          <div className="flex items-center gap-1 rounded-xl bg-surface-muted p-1">
            <button
              type="button"
              onClick={() => setDraft({ payNow: true })}
              className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-colors ${draft.payNow ? 'bg-white text-ink' : 'text-muted'}`}
            >
              Pay now
            </button>
            <button
              type="button"
              onClick={() => setDraft({ payNow: false })}
              className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-colors ${!draft.payNow ? 'bg-white text-ink' : 'text-muted'}`}
            >
              Check in, pay later
            </button>
          </div>

          {draft.payNow && (
            <div className="flex flex-col gap-2">
              {PAYMENT_METHODS.map((m) => {
                const active = draft.paymentMethod === m.id
                const Icon = METHOD_ICONS[m.id]
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setDraft({ paymentMethod: m.id })}
                    className={`flex items-center gap-3 rounded-xl px-3.5 py-3 text-left transition-colors ${
                      active ? 'bg-ink' : 'bg-white hover:bg-surface-muted'
                    }`}
                  >
                    <span
                      className={`flex size-9 shrink-0 items-center justify-center rounded-full ${
                        active ? 'bg-white/15 text-white' : 'bg-surface-muted text-ink'
                      }`}
                    >
                      <Icon size={17} strokeWidth={1.75} />
                    </span>
                    <span className="flex flex-col">
                      <span className={`text-sm font-bold ${active ? 'text-white' : 'text-ink'}`}>{m.name}</span>
                      <span className={`text-xs ${active ? 'text-white/60' : 'text-muted'}`}>{m.hint}</span>
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => onEditStep(1)}
            className="flex h-[clamp(2.75rem,4.5vw,3.125rem)] shrink-0 items-center justify-center rounded-xl bg-surface px-6 text-sm font-semibold text-ink hover:bg-surface-muted"
          >
            Edit
          </button>
          <button
            type="button"
            disabled={processing || !pricingReady}
            onClick={onPay}
            className="flex h-[clamp(2.75rem,4.5vw,3.125rem)] flex-1 items-center justify-center gap-2 rounded-xl bg-ink text-sm font-bold text-white disabled:opacity-50"
          >
            {processing ? (
              'Creating booking…'
            ) : (
              <>
                {draft.payNow ? `Charge ${money(invoice.total)}` : `Check in · ${money(invoice.total)} due`}
                <img src={arrowRight} alt="" className="size-[1.125rem]" />
              </>
            )}
          </button>
        </div>
        <p className="text-center text-[11px] text-muted">
          {draft.payNow
            ? 'Payment is recorded immediately against this booking.'
            : 'The booking is created as due and can be settled later at checkout.'}
        </p>
      </div>
    </div>
  )
}
