import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { components } from '../api/schema'

export type CheckinBooking = components['schemas']['BookingDetail']

const rank = (status: string) => (status === 'active' ? 0 : status === 'upcoming' ? 1 : status === 'overdue' ? 2 : 3)

/** Finds the most relevant live booking for a phone number just cleared by OTP — active
 *  right now beats upcoming-later, which beats anything already closed out. `getBooking`
 *  (not the list item) so the result card can show sport/court names, not just ids. */
export function useFindBookingByPhone(phone: string | null) {
  return useQuery({
    queryKey: ['checkin-booking-by-phone', phone],
    queryFn: async () => {
      const res = await api.listBookings({ search: phone!, size: 15 })
      const live = (res.items ?? []).filter((b) => b.status !== 'cancelled' && b.status !== 'completed')
      if (live.length === 0) return null

      live.sort((a, b) => {
        const r = rank(a.status) - rank(b.status)
        return r !== 0 ? r : new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
      })

      return api.getBooking(live[0].id)
    },
    enabled: !!phone,
    retry: false,
    staleTime: 0,
  })
}

export const maskPhone = (phone: string) =>
  phone.length > 4 ? `${phone.slice(0, 2)}${'*'.repeat(phone.length - 4)}${phone.slice(-2)}` : phone

export const timeLabel = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })

export const bookingTypeLabel = (type: string) => (type === 'online' ? 'Booked online' : 'Booked at the counter')
