import { money, type Draft } from '../../data/booking'
import { buildInvoice } from '../invoice'
import { downloadInvoicePdf } from '../../lib/invoicePdf'
import InvoiceDocument from '../InvoiceDocument'
import BookingTicket from '../BookingTicket'
import { STEPS } from '../Stepper'

export default function PaymentStep({
  draft,
  processing,
  onPay,
  onEditStep,
}: {
  draft: Draft
  processing: boolean
  onPay: () => void
  onEditStep: (step: number) => void
}) {
  const invoice = buildInvoice(draft)

  return (
    <div className="flex w-full flex-col gap-5 lg:flex-row lg:items-start">
      <div className="min-w-0 flex-1">
        <InvoiceDocument invoice={invoice} onDownloadPdf={() => downloadInvoicePdf(invoice)} />
      </div>

      <div className="flex w-full flex-col gap-4 lg:w-[380px] lg:shrink-0">
        <BookingTicket invoice={invoice} />

        <div className="flex w-full flex-col gap-1 rounded-xl bg-white p-4">
          {STEPS.map((label, i) => {
            const step = i + 1
            const done = step < 5
            return (
              <button
                key={label}
                type="button"
                onClick={() => onEditStep(step)}
                className="flex items-center gap-2.5 rounded-lg px-1.5 py-1.5 text-left hover:bg-surface-muted"
              >
                <span
                  className={`flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
                    done ? 'bg-lime text-lime-ink' : 'bg-ink text-white'
                  }`}
                >
                  {step}
                </span>
                <span className="text-sm text-ink">{label}</span>
              </button>
            )
          })}
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => onEditStep(1)}
            className="flex h-12 shrink-0 items-center justify-center rounded-full border border-border-input bg-white px-6 text-sm font-medium text-ink"
          >
            Edit
          </button>
          <button
            type="button"
            disabled={processing}
            onClick={onPay}
            className="flex h-12 flex-1 items-center justify-center gap-2 rounded-full text-sm text-[#fefefe] shadow-[0px_4px_10px_0px_rgba(0,0,0,0.05),0px_10px_120px_0px_rgba(15,73,106,0.1)] disabled:opacity-70"
            style={{ backgroundImage: 'linear-gradient(105deg, rgb(41,41,41) 2%, rgb(26,26,26) 100%)' }}
          >
            {processing ? 'Creating booking…' : `Create booking · ${money(invoice.total)}`}
          </button>
        </div>
        <p className="text-center text-[11px] text-muted">
          The booking is created as a due payment and can be settled later from the active court checkout.
        </p>
      </div>
    </div>
  )
}
