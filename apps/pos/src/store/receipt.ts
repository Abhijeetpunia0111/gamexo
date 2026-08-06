import { FACILITY_PROFILE } from '../facility/facilityData'
import { formalDate, toISO } from '../lib/format'
import type { EquipmentItem } from '../api/hooks'
import type { InvoiceData } from '../booking/invoice'

/** A kit-only sale has no court and no backing booking — the API has nowhere to store an
 *  anonymous sale yet, so this stays a local counter receipt (same limitation the admin
 *  dashboard's own "Sales" screen has today). Attaching kit to a booking in play, by
 *  contrast, goes through the real API — see CheckoutSheet's other tab. */
export function buildQuickSaleReceipt(
  tray: Record<string, number>,
  items: EquipmentItem[],
  customer: { name: string; phone: string; email: string; customerId: string },
  paidNow: boolean,
): InvoiceData {
  const lines = Object.entries(tray)
    .filter(([, qty]) => qty > 0)
    .map(([id, qty]) => {
      const item = items.find((i) => i.id === id)!
      return { label: item.name, detail: `× ${qty}`, amount: item.price * qty }
    })
  const subtotal = lines.reduce((sum, l) => sum + l.amount, 0)
  const gst = Math.round(subtotal * 0.18)
  const cgst = Math.round(gst / 2)
  const total = subtotal + gst
  const today = toISO(new Date())

  return {
    facility: FACILITY_PROFILE,
    invoiceNo: null,
    bookingId: null,
    confirmed: true,
    sportName: '',
    courtName: '',
    date: today,
    dateLabel: 'Today',
    formalDate: formalDate(today),
    timeRange: null,
    duration: '',
    customer: { ...customer, players: '' },
    items: lines,
    subtotal,
    discount: 0,
    gst,
    cgst,
    sgst: gst - cgst,
    total,
    amountPaid: paidNow ? total : 0,
    balanceDue: paidNow ? 0 : total,
    paymentMethod: null,
  }
}
