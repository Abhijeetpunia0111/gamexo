import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../api/client'
import type { components } from '../api/schema'

export type CheckinBooking = components['schemas']['BookingDetail']

/**
 * Resolve a typed Booking ID to the booking.
 *
 * A mutation rather than a query, because this fires on a button press and its
 * result is a screen transition — not state that should refetch, cache, or re-run
 * when the component happens to remount.
 *
 * Replaced `useFindBookingByPhone`, which searched every booking for a phone number
 * and then guessed which one the customer meant by ranking active over upcoming.
 * A reference identifies exactly one booking, so there is nothing left to guess.
 */
export function useLookupBooking() {
  return useMutation({
    mutationFn: (reference: string) => api.lookupBooking(reference),
  })
}

/** What to put on screen when a lookup fails.
 *
 *  A 404 is the ordinary case here — mistyped code, wrong academy's ticket, phone
 *  number typed out of habit — so it reads as a prompt to try again rather than as
 *  something being broken. Anything else genuinely is. */
export function lookupErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.isNotFound) {
    return "We couldn't find that Booking ID. Check it and try again."
  }
  return 'Something went wrong looking that up. Please ask at the counter.'
}

/** Looks a booking up by the id typed on the check-in keyboard. The backend already
 *  scopes this to bookings starting within 30 minutes either side of now and 404s
 *  otherwise — that 404 is a normal "not found" result here, not a query error. */
export function useFindBookingByCode(code: string | null) {
  return useQuery({
    queryKey: ['checkin-booking-by-code', code],
    queryFn: async () => {
      try {
        return await api.checkinLookup(code!.trim())
      } catch (err) {
        if (err instanceof ApiError && err.isNotFound) return null
        throw err
      }
    },
    enabled: !!code,
    retry: false,
    staleTime: 0,
  })
}

export const timeLabel = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })

export const bookingTypeLabel = (type: string) =>
  type === 'online' ? 'Booked online' : 'Booked at the counter'
