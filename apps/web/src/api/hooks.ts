/**
 * Query hooks + the mapping layer between API shapes and the shapes the existing
 * screens already render.
 *
 * The mapping lives here on purpose. Screens keep consuming `Sport`/`Court` as
 * they always have, so wiring one up is a swap of the data source rather than a
 * rewrite of its JSX — and this file is the only place that knows the API uses
 * UUIDs, decimal strings and no sport imagery.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'
import type { Booking, Court, Sport } from '../data/booking'

import football from '../assets/figma/sports/football.png'
import cricket from '../assets/figma/sports/cricket.png'
import tennis from '../assets/figma/sports/tennis.png'
import badminton from '../assets/figma/sports/badminton.png'
import pickleball from '../assets/figma/sports/pickleball.png'
import tableTennis from '../assets/figma/sports/table-tennis.png'

type SportOut = components['schemas']['SportOut']
type CourtWithStatus = components['schemas']['CourtWithStatus']
type BookingOut = components['schemas']['BookingOut']

/**
 * The API has no sport imagery — it carries `icon`/`color`, while the UI is built
 * around these photographs. Matched on slug, so a sport the backend adds that we
 * have no art for still renders (without a photo) rather than breaking the grid.
 */
const SPORT_IMAGES: Record<string, string> = {
  football,
  cricket,
  tennis,
  badminton,
  pickleball,
  'table-tennis': tableTennis,
  tabletennis: tableTennis,
}

/** Money crosses the wire as a decimal string; JS renders a number. */
const money = (v: string | number | null | undefined) => Number(v ?? 0)

export function toSport(s: SportOut, courtCount?: number): Sport {
  return {
    id: s.id,
    name: s.name,
    fieldsLabel: courtCount === undefined ? '' : `${courtCount} ${courtCount === 1 ? 'Court' : 'Courts'}`,
    from: money(s.price_base),
    image: SPORT_IMAGES[s.slug] ?? '',
  }
}

export function toCourt(c: CourtWithStatus): Court {
  const hours = c.operating_hours ?? { open: '06:00', close: '22:00' }
  return {
    id: c.id,
    sportId: c.sport_id,
    name: c.name,
    price: money(c.hourly_rate),
    surface: c.sport_name ?? '',
    // Ratings are presentational in the mock data and have no API equivalent yet.
    rating: 0,
    reviews: 0,
    capacity: 0,
    amenities: c.amenities ?? [],
    hours: `${hours.open} – ${hours.close}`,
  }
}

/**
 * The two status vocabularies do not line up: the API tracks a booking's lifecycle
 * (`upcoming`/`active`/`overdue`), the UI tracks what the counter staff see
 * (`confirmed`/`checked-in`). `overdue` has no UI equivalent and reads as still
 * playing, so it maps to checked-in rather than being dropped.
 */
const BOOKING_STATUS: Record<string, Booking['status']> = {
  upcoming: 'confirmed',
  active: 'checked-in',
  overdue: 'checked-in',
  completed: 'completed',
  cancelled: 'completed',
}

export function toBooking(b: BookingOut): Booking {
  const starts = new Date(b.starts_at)
  // Local date parts, not toISOString() — that would shift an evening booking in
  // IST back to the previous day and file it under the wrong date.
  const date = `${starts.getFullYear()}-${String(starts.getMonth() + 1).padStart(2, '0')}-${String(
    starts.getDate(),
  ).padStart(2, '0')}`

  const equipment: Record<string, number> = {}
  for (const line of b.equipment ?? []) equipment[line.name] = line.qty

  return {
    id: b.id,
    sportId: b.sport_id,
    courtId: b.court_id,
    date,
    startHour: starts.getHours(),
    hours: (b.duration_min ?? 60) / 60,
    customer: {
      name: b.customer_name ?? '',
      phone: b.customer_phone ?? '',
      email: '',
      players: '',
      notes: b.notes ?? '',
    },
    equipment,
    slotTotal: money(b.court_charge),
    equipmentTotal: money(b.equipment_charge),
    subtotal: money(b.court_charge) + money(b.equipment_charge) - money(b.discount),
    gst: money(b.taxes),
    total: money(b.total),
    paidTotal: money(b.amount_paid),
    payment: b.payment_method ? { method: b.payment_method, status: b.payment_status ?? 'due' } : null,
    status: BOOKING_STATUS[b.status ?? 'upcoming'] ?? 'confirmed',
    source: b.booking_type === 'online' ? 'app' : 'counter',
    createdAt: b.created_at,
  }
}

export const queryKeys = {
  sports: ['sports'] as const,
  courts: (sportId?: string) => ['courts', sportId ?? 'all'] as const,
  bookings: (page: number) => ['bookings', page] as const,
}

/** Sports, with each one's court count folded in for the "N Courts" label. */
export function useSports() {
  const courts = useQuery({ queryKey: queryKeys.courts(), queryFn: () => api.listCourts() })

  return useQuery({
    queryKey: [...queryKeys.sports, courts.data?.length ?? 0],
    queryFn: async () => {
      const sports = await api.listSports()
      const counts = new Map<string, number>()
      for (const c of courts.data ?? []) counts.set(c.sport_id, (counts.get(c.sport_id) ?? 0) + 1)
      return sports.map((s) => toSport(s, counts.get(s.id) ?? 0))
    },
    enabled: !courts.isLoading,
  })
}

export function useCourts(sportId?: string) {
  return useQuery({
    queryKey: queryKeys.courts(sportId),
    queryFn: async () => (await api.listCourts(sportId ? { sport_id: sportId } : undefined)).map(toCourt),
  })
}

/** Returns the page envelope with `items` already mapped to the UI's Booking shape. */
export function useBookings(page = 1, size = 50) {
  return useQuery({
    queryKey: queryKeys.bookings(page),
    queryFn: async () => {
      const res = await api.listBookings({ page, size })
      return { ...res, items: (res.items ?? []).map(toBooking) }
    },
  })
}

/**
 * Settle a booking's outstanding balance. Invalidates the booking list so the row
 * reflects the payment — the old localStorage write updated the same array the list
 * rendered from, which a server-backed list does not get for free.
 */
export function useRecordPayment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { bookingId: string; amount: number; method: 'cash' | 'upi' | 'card' | 'bank' | 'cheque' }) =>
      api.recordPayment({ booking_id: vars.bookingId, amount: vars.amount, method: vars.method }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['bookings'] }),
  })
}
