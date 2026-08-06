import * as db from '../lib/db'
import football from '../assets/figma/sports/football.png'
import cricket from '../assets/figma/sports/cricket.png'
import tennis from '../assets/figma/sports/tennis.png'
import badminton from '../assets/figma/sports/badminton.png'
import pickleball from '../assets/figma/sports/pickleball.png'
import tableTennis from '../assets/figma/sports/table-tennis.png'

export const GST_RATE = 0.18
export const VENUE_OPENS = 6
export const VENUE_CLOSES = 24

export type Sport = {
  id: string
  name: string
  fieldsLabel: string
  from: number
  image: string
}

export const SPORTS: Sport[] = [
  { id: 'football', name: 'Football', fieldsLabel: '6 Fields', from: 800, image: football },
  { id: 'cricket', name: 'Cricket', fieldsLabel: '6 Fields', from: 800, image: cricket },
  { id: 'tennis', name: 'Tennis', fieldsLabel: '6 Fields', from: 800, image: tennis },
  { id: 'badminton', name: 'Badminton', fieldsLabel: '6 Fields', from: 800, image: badminton },
  { id: 'pickleball', name: 'Pickleball', fieldsLabel: '6 Fields', from: 800, image: pickleball },
  { id: 'tabletennis', name: 'Table Tennis', fieldsLabel: '6 Fields', from: 800, image: tableTennis },
]

export type Court = {
  id: string
  sportId: string
  name: string
  price: number
  surface: string
  rating: number
  reviews: number
  capacity: number
  amenities: string[]
  hours: string
}

const courtsFor = (
  sportId: string,
  surface: string,
  price: number,
  capacity: number,
  amenities: string[],
): Court[] =>
  (['A', 'B', 'C', 'D'] as const).map((letter, i) => ({
    id: `${sportId}-${letter.toLowerCase()}`,
    sportId,
    name: `Court ${letter}`,
    price,
    surface,
    rating: [4.6, 4.4, 4.8, 4.2][i],
    reviews: [214, 96, 301, 58][i],
    capacity,
    amenities,
    hours: `${VENUE_OPENS} AM – 12 AM`,
  }))

export const COURTS: Court[] = [
  ...courtsFor('football', 'Artificial Turf', 800, 14, ['Floodlights', 'Changing room', 'Parking']),
  ...courtsFor('cricket', 'Matting over concrete', 800, 16, ['Bowling machine', 'Floodlights', 'Scoreboard']),
  ...courtsFor('tennis', 'Artificial Turf', 800, 4, ['Floodlights', 'Changing room', 'Parking']),
  ...courtsFor('badminton', 'BWF synthetic mat', 800, 4, ['Air conditioning', 'Locker', 'Parking']),
  ...courtsFor('pickleball', 'Cushioned acrylic', 800, 4, ['Floodlights', 'Paddles included', 'Parking']),
  ...courtsFor('tabletennis', 'Stag tournament table', 800, 4, ['Air conditioning', 'Locker', 'Parking']),
]

export const sportById = (id: string) => SPORTS.find((s) => s.id === id)
export const courtById = (id: string) => COURTS.find((c) => c.id === id)
export const courtsForSport = (id: string) => COURTS.filter((c) => c.sportId === id)

/** Same in-place swap as `setEquipmentCatalog` below, for sports and courts.
 *
 *  The booking wizard picks from the API (see `useSports`/`useCourts`), so the ids
 *  it puts in a draft are UUIDs, while the seed rows above are keyed by slug
 *  (`football-a`). Until these are repointed, every `courtById`/`sportById` lookup
 *  behind the wizard's pricing, its slot grid and its invoice misses — rendering a
 *  nameless court at ₹0 rather than failing loudly. `SportCourtBridge` does the
 *  repointing once, near the root. */
export function setSportCatalog(items: Sport[]) {
  SPORTS.length = 0
  SPORTS.push(...items)
}

export function setCourtCatalog(items: Court[]) {
  COURTS.length = 0
  COURTS.push(...items)
}

export type Equipment = {
  id: string
  name: string
  price: number
  sports: string[]
  hint: string
  stock: number
  /** Handed back at the end of the session and tracked as a rental, not a one-off sale. */
  returnable: boolean
  deposit?: number
}

/** Seed data — shown only until the real, published Inventory catalogue loads and
 *  overwrites these contents in place (see `setEquipmentCatalog` and
 *  `inventory/PublishedEquipmentBridge.tsx`). Every shop-facing screen (Add-ons,
 *  the walk-in booking flow, Active Courts' kit panel) reads through functions
 *  further down this file, never this array directly, so the swap is invisible
 *  to them. */
export const EQUIPMENT: Equipment[] = [
  { id: 'shoes', name: 'Studs / Shoes', price: 120, sports: ['football', 'cricket'], hint: 'Sizes 5–12', stock: 24, returnable: true, deposit: 300 },
  { id: 'football', name: 'Football', price: 250, sports: ['football'], hint: 'Size 5, match ball', stock: 12, returnable: false },
  { id: 'bib', name: 'Team Bibs', price: 60, sports: ['football'], hint: 'Set of 7', stock: 40, returnable: true, deposit: 200 },
  { id: 'racket', name: 'Racket', price: 80, sports: ['badminton', 'tennis', 'pickleball'], hint: 'Strung', stock: 20, returnable: true, deposit: 400 },
  { id: 'shuttle', name: 'Shuttlecock', price: 40, sports: ['badminton'], hint: 'Tube of 3', stock: 60, returnable: false },
  { id: 'bat', name: 'Cricket Bat', price: 200, sports: ['cricket'], hint: 'English willow', stock: 10, returnable: true, deposit: 500 },
  { id: 'pads', name: 'Pads & Gloves', price: 150, sports: ['cricket'], hint: 'Batting set', stock: 8, returnable: true, deposit: 400 },
  { id: 'paddle', name: 'Paddle', price: 90, sports: ['pickleball', 'tabletennis'], hint: 'Composite face', stock: 14, returnable: true, deposit: 300 },
  { id: 'coach', name: 'Coach', price: 500, sports: ['football', 'cricket', 'tennis', 'badminton'], hint: 'Per hour, book ahead', stock: 3, returnable: false },
  { id: 'towel', name: 'Towel', price: 30, sports: [], hint: 'Fresh, cotton', stock: 50, returnable: false },
  { id: 'bottle', name: 'Water Bottle', price: 20, sports: [], hint: '1 litre, chilled', stock: 100, returnable: false },
  { id: 'locker', name: 'Locker', price: 50, sports: [], hint: 'For the full slot', stock: 30, returnable: true, deposit: 200 },
]

/** Repoints the shared catalogue at what Inventory has actually published, in
 *  place, so every existing reader (`equipmentForSport`, `priceEquipment`, the
 *  Active Courts kit panel, ...) picks it up without a single call site changing. */
export function setEquipmentCatalog(items: Equipment[]) {
  EQUIPMENT.length = 0
  EQUIPMENT.push(...items)
}

export const equipmentById = (id: string) => EQUIPMENT.find((e) => e.id === id)

/** The catalogue's base numbers, layered with whatever an admin has changed from Inventory —
 *  stock on hand, whether it's offered in the shop, and which sports it's linked to. Every
 *  shop-facing list (booking add-ons, the counter, category chips) reads through this, not
 *  the raw catalogue, so an admin edit shows up everywhere at once. */
export function listEquipment(): (Equipment & { activeForSale: boolean })[] {
  return EQUIPMENT.map((item) => {
    const override = db.getEquipmentOverride(item.id, {
      stock: item.stock,
      activeForSale: true,
      sports: item.sports,
      name: item.name,
      hint: item.hint,
      price: item.price,
      returnable: item.returnable,
      deposit: item.deposit,
    })
    return {
      ...item,
      stock: override.stock,
      sports: override.sports,
      activeForSale: override.activeForSale,
      name: override.name || item.name,
      hint: override.hint || item.hint,
      price: override.price ?? item.price,
      returnable: override.returnable ?? item.returnable,
      deposit: override.deposit ?? item.deposit,
    }
  })
}

export const equipmentInShop = () => listEquipment().filter((e) => e.activeForSale)

export const equipmentForSport = (sportId: string) =>
  equipmentInShop().filter((e) => e.sports.length === 0 || e.sports.includes(sportId))

/** Category chips for the Add-ons catalogue: All, then each sport with kit, then General. */
export function equipmentCategories() {
  const shop = equipmentInShop()
  const sportIds = SPORTS.filter((s) => shop.some((e) => e.sports.includes(s.id))).map((s) => ({
    id: s.id,
    label: s.name,
  }))
  const hasGeneral = shop.some((e) => e.sports.length === 0)
  return [{ id: 'all', label: 'All' }, ...sportIds, ...(hasGeneral ? [{ id: 'general', label: 'General' }] : [])]
}

export function equipmentForCategory(categoryId: string) {
  const shop = equipmentInShop()
  if (categoryId === 'all') return shop
  if (categoryId === 'general') return shop.filter((e) => e.sports.length === 0)
  return shop.filter((e) => e.sports.includes(categoryId))
}

export type PaymentMethod = { id: string; name: string; hint: string }

export const PAYMENT_METHODS: PaymentMethod[] = [
  { id: 'upi', name: 'UPI', hint: 'GPay, PhonePe, Paytm' },
  { id: 'card', name: 'Card', hint: 'Visa, Mastercard, RuPay' },
  { id: 'cash', name: 'Cash', hint: 'Collect at the counter' },
  { id: 'wallet', name: 'Wallet', hint: 'Arena credit' },
]

/* ---------- slots ---------- */

function hash(str: string) {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

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

export type SlotState = 'open' | 'booked' | 'past'

/** Deterministic per court/date/hour so availability never flickers between renders. */
export function slotState(courtId: string, iso: string, hour: number): SlotState {
  const now = new Date()
  const todayISO = toISO(now)
  if (iso < todayISO) return 'past'
  if (iso === todayISO && hour <= now.getHours()) return 'past'
  const n = hash(`${courtId}|${iso}|${hour}`) % 100
  const pressure = hour >= 17 && hour < 22 ? 46 : hour >= 12 && hour < 17 ? 20 : 14
  return n < pressure ? 'booked' : 'open'
}

export function slotsForDay(courtId: string, iso: string) {
  const out: { hour: number; state: SlotState }[] = []
  for (let h = VENUE_OPENS; h < VENUE_CLOSES; h++) out.push({ hour: h, state: slotState(courtId, iso, h) })
  return out
}

export const pad = (n: number) => String(n).padStart(2, '0')
export const slotChipLabel = (hour: number) => `${pad(hour)}:00`

export function hour12(hour: number) {
  const h = hour % 24
  const suffix = h < 12 ? 'AM' : 'PM'
  const display = h % 12 === 0 ? 12 : h % 12
  return `${display} ${suffix}`
}

export function rangeLabel(startHour: number, hours: number) {
  return `${hour12(startHour)} – ${hour12(startHour + hours)}`
}

const inr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
export const money = (n: number) => `₹${inr.format(Math.round(n || 0))}`

/* ---------- pricing ---------- */

export type Draft = {
  sportId: string | null
  courtId: string | null
  date: string | null
  startHour: number | null
  hours: number
  customer: { name: string; phone: string; email: string; players: string; notes: string }
  equipment: Record<string, number>
  payment: string | null
}

export const emptyDraft = (): Draft => ({
  sportId: null,
  courtId: null,
  date: null,
  startHour: null,
  hours: 1,
  customer: { name: '', phone: '', email: '', players: '', notes: '' },
  equipment: {},
  payment: null,
})

export function equipmentLines(equipment: Record<string, number>) {
  return Object.entries(equipment)
    .filter(([, qty]) => qty > 0)
    .map(([id, qty]) => {
      // The catalogue is live now (see setEquipmentCatalog) — an older booking can
      // reference an id that's since been unpublished or removed. Show it as a
      // priceless line rather than crashing the screen it's rendered on.
      const item = EQUIPMENT.find((e) => e.id === id)
      return { id, name: item?.name ?? 'Removed item', qty, amount: (item?.price ?? 0) * qty }
    })
}

/** One pricing function for kit alone — the counter tray, or a booking's add-ons. */
export function priceEquipment(equipment: Record<string, number>) {
  const lines = equipmentLines(equipment)
  const equipmentTotal = lines.reduce((sum, l) => sum + l.amount, 0)
  const gst = Math.round(equipmentTotal * GST_RATE)
  return { lines, equipmentTotal, gst, total: equipmentTotal + gst }
}

export function priceDraft(draft: Draft) {
  const court = draft.courtId ? courtById(draft.courtId) : null
  const slotTotal = (court?.price || 0) * draft.hours
  const { lines, equipmentTotal } = priceEquipment(draft.equipment)
  const subtotal = slotTotal + equipmentTotal
  const gst = Math.round(subtotal * GST_RATE)
  return { slotTotal, lines, equipmentTotal, subtotal, gst, total: subtotal + gst }
}

/* ---------- persisted records ---------- */

export type Customer = { name: string; phone: string; email: string; visits: number }

export type Booking = {
  id: string
  sportId: string
  courtId: string
  date: string
  startHour: number
  hours: number
  customer: { name: string; phone: string; email: string; players: string; notes: string }
  equipment: Record<string, number>
  slotTotal: number
  equipmentTotal: number
  subtotal: number
  gst: number
  total: number
  paidTotal: number
  payment: { method: string; status: string } | null
  status: 'checked-in' | 'confirmed' | 'completed'
  source: 'app' | 'counter'
  createdAt: string
}

export type Sale = {
  id: string
  customer: { name: string; phone: string; email: string }
  equipment: Record<string, number>
  equipmentTotal: number
  gst: number
  total: number
  paidTotal: number
  payment: { method: string; status: string } | null
  createdAt: string
}

export const balanceOf = (row: { total: number; paidTotal: number }) => Math.max(0, Math.round(row.total - row.paidTotal))

/** One returnable item, out with one customer. The source of truth for "issued" —
 *  nothing else tracks that count separately, it's always summed from open rentals. */
export type Rental = {
  id: string
  itemId: string
  qty: number
  deposit: number
  customer: { name: string; phone: string }
  issuedAt: string
  dueBackAt: string
  status: 'out' | 'returned' | 'lost' | 'maintenance'
  returnedAt: string | null
}

/** Kit handed over after play has started — total moves, what's already paid doesn't. */
export function withExtras(booking: Booking, add: Record<string, number>): Booking {
  const equipment = { ...booking.equipment }
  for (const [id, qty] of Object.entries(add)) {
    const next = (equipment[id] || 0) + qty
    if (next > 0) equipment[id] = next
    else delete equipment[id]
  }
  const { equipmentTotal } = priceEquipment(equipment)
  const subtotal = booking.slotTotal + equipmentTotal
  const gst = Math.round(subtotal * GST_RATE)
  return { ...booking, equipment, equipmentTotal, subtotal, gst, total: subtotal + gst }
}

/** Pushes a booking's end time out by an hour — caller is responsible for checking the next slot is free. */
export function extendByHour(booking: Booking): Booking {
  const court = courtById(booking.courtId)!
  const hours = booking.hours + 1
  const slotTotal = court.price * hours
  const subtotal = slotTotal + booking.equipmentTotal
  const gst = Math.round(subtotal * GST_RATE)
  return { ...booking, hours, slotTotal, subtotal, gst, total: subtotal + gst }
}

/** A few games already on the floor, anchored to the current hour, so Add-ons
 *  has something real to attach a tray to on first run. */
export function demoBookings(): Booking[] {
  const iso = toISO(new Date())
  const names: [string, string][] = [
    ['Ananya Rao', '9845012233'],
    ['Vikram Shetty', '9900112244'],
    ['Farah Qureshi', '9663344556'],
    ['Dev Menon', '9812233445'],
    ['Ishita Bose', '9701122334'],
  ]
  const H = Math.min(21, Math.max(VENUE_OPENS + 1, new Date().getHours()))
  const picks: { courtId: string; startHour: number; hours: number; status: Booking['status'] }[] = [
    { courtId: 'football-a', startHour: H - 1, hours: 1, status: 'checked-in' },
    { courtId: 'badminton-a', startHour: H, hours: 1, status: 'checked-in' },
    { courtId: 'tennis-b', startHour: H, hours: 2, status: 'checked-in' },
    { courtId: 'cricket-a', startHour: H + 1, hours: 1, status: 'confirmed' },
    { courtId: 'pickleball-a', startHour: H + 1, hours: 1, status: 'confirmed' },
  ]
  return picks.map((p, i) => {
    const court = courtById(p.courtId)!
    const slotTotal = court.price * p.hours
    const gst = Math.round(slotTotal * GST_RATE)
    return {
      id: `NV${70000 + i * 137}`,
      sportId: court.sportId,
      courtId: p.courtId,
      date: iso,
      startHour: p.startHour,
      hours: p.hours,
      customer: { name: names[i][0], phone: names[i][1], email: '', players: '4', notes: '' },
      equipment: {},
      slotTotal,
      equipmentTotal: 0,
      subtotal: slotTotal,
      gst,
      total: slotTotal + gst,
      paidTotal: slotTotal + gst,
      payment: { method: 'upi', status: 'paid' },
      status: p.status,
      source: 'app',
      createdAt: new Date(Date.now() - (5 - i) * 3600_000).toISOString(),
    }
  })
}
