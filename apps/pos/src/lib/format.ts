// Two decimals, always. The API returns every amount as a NUMERIC(12,2) string, so
// ₹334.80 of GST is exactly ₹334.80 — rounding it to ₹335 for display put the
// counter screen out of step with the ledger and with the invoice the customer is
// handed. `minimumFractionDigits` keeps ₹1,600.00 from collapsing to "₹1,600" and
// breaking decimal alignment down a column of amounts.
const inr = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
export const money = (n: number | string | null | undefined) => `₹${inr.format(Number(n) || 0)}`

/**
 * Round to paise — NOT to rupees.
 *
 * For clearing IEEE-754 residue after arithmetic on money, so a settled bill reads
 * as 0 rather than 4.5e-14. Never use it to drop paise off a real amount.
 */
export const toPaise = (n: number) => Math.round(n * 100) / 100

export const toISO = (d: Date) => {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
  return z.toISOString().slice(0, 10)
}

export function nextDays(count = 7) {
  const out = []
  const base = new Date()
  base.setHours(0, 0, 0, 0)
  for (let i = 0; i < count; i++) {
    const d = new Date(base)
    d.setDate(base.getDate() + i)
    out.push({
      iso: toISO(d),
      dayNum: d.getDate(),
      monthShort: d.toLocaleDateString('en-IN', { month: 'short' }),
      label: i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : d.toLocaleDateString('en-IN', { weekday: 'short' }),
    })
  }
  return out
}

export const pad = (n: number) => String(n).padStart(2, '0')
export const slotChipLabel = (hour: number) => `${pad(hour)}:00`

export function hour12(hour: number) {
  const h = ((hour % 24) + 24) % 24
  const suffix = h < 12 ? 'AM' : 'PM'
  const display = h % 12 === 0 ? 12 : h % 12
  return `${display} ${suffix}`
}

export function rangeLabel(startHour: number, hours: number) {
  return `${hour12(startHour)} – ${hour12(startHour + hours)}`
}

/** Today / Tomorrow / "Wed, 12 Aug" — matches the relative-day chips used in the date picker. */
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

/** Builds a local (venue-timezone) ISO datetime for `date` (yyyy-mm-dd) at `hour` — what the
 *  API's `starts_at` expects. Browsers serialize `Date` in local time when built from parts,
 *  and `toISOString()` below converts to the correct UTC instant either way. */
export function startsAtISO(dateIso: string, hour: number) {
  const [y, m, d] = dateIso.split('-').map(Number)
  return new Date(y, m - 1, d, hour, 0, 0, 0).toISOString()
}
