import { FACILITY_PROFILE } from '../facility/facilityData'
import { courtById, hour12, money, priceDraft, sportById, toISO, type Draft } from '../data/booking'

/** Today / Tomorrow / "Wed, 12 Aug" — matches the relative-day chips used elsewhere in booking. */
export function dayLabel(iso: string) {
  const d = new Date(iso + 'T00:00:00')
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diffDays = Math.round((d.getTime() - today.getTime()) / 86_400_000)
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Tomorrow'
  return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
}

/** "01 Aug 2026" — the formal date used on the printed/PDF invoice header. */
export function formalDate(iso: string) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function buildInvoice(draft: Draft, opts: { bookingId?: string | null } = {}) {
  const court = draft.courtId ? courtById(draft.courtId) : null
  const sport = draft.sportId ? sportById(draft.sportId) : null
  const totals = priceDraft(draft)
  // GST is a flat 18% in the pricing model; split evenly into CGST/SGST for the invoice line items.
  const cgst = Math.round(totals.gst / 2)
  const sgst = totals.gst - cgst
  const date = draft.date || toISO(new Date())
  const timeRange =
    draft.startHour != null ? `${hour12(draft.startHour)} – ${hour12(draft.startHour + draft.hours)}` : null

  const items = [
    ...(court
      ? [
          {
            label: `${court.name} — court hire`,
            detail: `${money(court.price)} × ${draft.hours} hr`,
            amount: totals.slotTotal,
          },
        ]
      : []),
    ...totals.lines.map((l) => ({ label: l.name, detail: `× ${l.qty}`, amount: l.amount })),
  ]

  return {
    facility: FACILITY_PROFILE,
    bookingId: opts.bookingId ?? null,
    court,
    sport,
    date,
    dateLabel: dayLabel(date),
    formalDate: formalDate(date),
    timeRange,
    duration: `${draft.hours} hr`,
    customer: draft.customer,
    items,
    subtotal: totals.subtotal,
    gst: totals.gst,
    cgst,
    sgst,
    total: totals.total,
  }
}

export type InvoiceData = ReturnType<typeof buildInvoice>

export function invoiceSummaryText(inv: InvoiceData) {
  const lines = [
    inv.facility.name,
    inv.bookingId ? `Booking ${inv.bookingId} · Confirmed` : 'Provisional invoice',
    `${inv.sport?.name ?? ''} · ${inv.court?.name ?? ''}`,
    `${inv.dateLabel}${inv.timeRange ? `, ${inv.timeRange}` : ''}`,
    '',
    ...inv.items.map((i) => `${i.label} — ${money(i.amount)}`),
    '',
    `Subtotal: ${money(inv.subtotal)}`,
    `CGST 9%: ${money(inv.cgst)}`,
    `SGST 9%: ${money(inv.sgst)}`,
    `Total: ${money(inv.total)}`,
  ]
  return lines.join('\n')
}
