/**
 * What an add-on can be taken as, at the counter.
 *
 * One catalogue row produces up to three offers — rent by the hour, buy one, buy a
 * pack — because the same shuttlecock is three different sales. The tray therefore
 * keys on the *offer*, not the item: renting a racket and buying one are two lines
 * at two prices and must not collapse into each other.
 *
 * Mirrors `EquipmentSelection` on the API, and `apps/web/src/addons/offers.ts`.
 */
import type { EquipmentItem } from '../api/hooks'
import { toPaise } from '../lib/format'

export type { EquipmentItem }

export type AddOnMode = 'rent' | 'buy'
export type AddOnUnit = 'single' | 'pack'

export type Offer = {
  key: string
  item: EquipmentItem
  mode: AddOnMode
  unit: AddOnUnit
  label: string
  price: number
  /** Base units off the shelf per one of these. A pack of three draws three. */
  draws: number
  /** Rentals bill per hour of play; purchases are one-off. */
  perHour: boolean
}

export function addOnKey(id: string, mode: AddOnMode = 'rent', unit: AddOnUnit = 'single') {
  return `${id}|${mode}|${unit}`
}

export function parseAddOnKey(key: string): { id: string; mode: AddOnMode; unit: AddOnUnit } {
  const [id, mode, unit] = key.split('|')
  return {
    id,
    mode: mode === 'buy' ? 'buy' : 'rent',
    unit: unit === 'pack' ? 'pack' : 'single',
  }
}

export function offersFor(item: EquipmentItem): Offer[] {
  const out: Offer[] = []

  // A zero rental rate means "not really lent" even where the flag is on — the
  // swimming kit is sold, not loaned, and must not appear as a free rental.
  if (item.forRent && item.price > 0) {
    out.push({
      key: addOnKey(item.id, 'rent', 'single'),
      item,
      mode: 'rent',
      unit: 'single',
      label: 'Rent',
      price: item.price,
      draws: 1,
      perHour: true,
    })
  }

  if (item.forSale) {
    out.push({
      key: addOnKey(item.id, 'buy', 'single'),
      item,
      mode: 'buy',
      unit: 'single',
      label: 'Buy',
      price: item.salePrice,
      draws: 1,
      perHour: false,
    })
    if (item.packSize > 1) {
      out.push({
        key: addOnKey(item.id, 'buy', 'pack'),
        item,
        mode: 'buy',
        unit: 'pack',
        label: `Pack of ${item.packSize}`,
        price: item.packPrice,
        draws: item.packSize,
        perHour: false,
      })
    }
  }

  return out
}

/** Base units an item's offers have already claimed — they share one stock pool. */
export function unitsClaimed(
  offers: Offer[],
  tray: Record<string, number>,
  itemId: string,
): number {
  return offers
    .filter((o) => o.item.id === itemId)
    .reduce((sum, o) => sum + (tray[o.key] || 0) * o.draws, 0)
}

/**
 * Price a tray, one line per offer.
 *
 * `hours` is how long a rental runs. A counter sale has no session behind it, so
 * it defaults to one hour — the same assumption the admin app makes. Purchases and
 * packs ignore it entirely.
 */
export function trayLines(tray: Record<string, number>, catalog: EquipmentItem[], hours = 1) {
  return Object.entries(tray)
    .filter(([, qty]) => qty > 0)
    .map(([key, qty]) => {
      const { id, mode, unit } = parseAddOnKey(key)
      const item = catalog.find((c) => c.id === id)
      // Resolve through offersFor so the price comes from the same place the card
      // showed it — no second opinion on what a pack costs.
      const offer = item ? offersFor(item).find((o) => o.key === key) : undefined
      const rate = offer?.price ?? 0
      const suffix =
        unit === 'pack' ? ` (pack of ${item?.packSize ?? 1})` : mode === 'buy' ? ' (purchase)' : ''
      const billed = offer?.perHour ? qty * hours : qty
      return {
        key,
        label: `${item?.name ?? 'Removed item'}${suffix}`,
        qty,
        rate,
        amount: toPaise(rate * billed),
      }
    })
}

export const trayTotal = (tray: Record<string, number>, catalog: EquipmentItem[], hours = 1) =>
  trayLines(tray, catalog, hours).reduce((sum, l) => sum + l.amount, 0)

/** Tray → the API's equipment selections. */
export function traySelections(tray: Record<string, number>) {
  return Object.entries(tray)
    .filter(([, qty]) => qty > 0)
    .map(([key, qty]) => {
      const { id, mode, unit } = parseAddOnKey(key)
      return { equipment_id: id, qty, mode, unit }
    })
}
