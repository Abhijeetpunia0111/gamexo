import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import QRCode from 'qrcode'
import { api, ApiError } from '../api/client'
import type { components } from '../api/schema'

export type CheckoutBooking = components['schemas']['BookingDetail']

/** A session can be settled once its slot has begun and it was not cancelled.
 *
 *  Goes by the actual clock rather than the `status` enum: nothing flips a booking
 *  from "upcoming" to "active" as its slot arrives, so a stored status of "upcoming"
 *  on a booking that started an hour ago means the enum is stale, not that the
 *  customer is absent — they are standing at the counter asking to pay. */
const settleable = (b: { status: string; starts_at: string }) =>
  b.status !== 'cancelled' && new Date(b.starts_at).getTime() <= Date.now()

/**
 * Find the session to settle from whatever the customer offers.
 *
 * Two passes, in this order:
 *
 * 1. **Exact booking reference.** `search` is a substring match, so it cannot find
 *    `XC-B-0042` from `42` or `XCB0042` — the lookup endpoint normalises those, and
 *    it is also the only path that guarantees one booking rather than a best guess.
 * 2. **Name or phone**, falling back to a search. Several may match, so the most
 *    recently started wins: that is the session in front of you.
 *
 * A mutation, not a query — it fires on a button press and its result is a screen
 * transition, not state that should refetch on remount.
 */
export function useFindSession() {
  return useMutation({
    mutationFn: async (query: string): Promise<CheckoutBooking | null> => {
      const trimmed = query.trim()
      if (!trimmed) return null

      try {
        const exact = await api.lookupBooking(trimmed)
        return settleable(exact) ? exact : null
      } catch (err) {
        // Not a reference, or not one of ours. Fall through to the broad search
        // rather than failing — anything else is a real error worth surfacing.
        if (!(err instanceof ApiError && err.isNotFound)) throw err
      }

      const res = await api.listBookings({ search: trimmed, size: 15 })
      const live = (res.items ?? []).filter(settleable)
      if (live.length === 0) return null
      live.sort((a, b) => new Date(b.starts_at).getTime() - new Date(a.starts_at).getTime())
      return api.getBooking(live[0].id)
    },
  })
}

/** How far past the booked slot "now" is — 0 if the session hasn't run over yet. */
export function extraMinutes(booking: CheckoutBooking) {
  const expectedEnd = new Date(booking.starts_at).getTime() + booking.duration_min * 60_000
  const overMs = Date.now() - expectedEnd
  return overMs > 60_000 ? Math.round(overMs / 60_000) : 0
}

export function durationLabel(minutes: number) {
  const hrs = minutes / 60
  return Number.isInteger(hrs) ? `${hrs} hr` : `${Math.floor(hrs)}h ${minutes % 60}m`
}

/** Renders a `upi://pay` deep link as a scannable QR — generated client-side (no backend
 *  round trip, no third-party QR image service seeing the payment reference). */
export function useUpiQrCode(vpa: string, amount: number, payeeName: string, note: string) {
  const [dataUrl, setDataUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!vpa) {
      setDataUrl(null)
      return
    }
    let cancelled = false
    const uri = `upi://pay?pa=${encodeURIComponent(vpa)}&pn=${encodeURIComponent(payeeName)}&am=${amount.toFixed(2)}&cu=INR&tn=${encodeURIComponent(note)}`
    QRCode.toDataURL(uri, { margin: 1, width: 480, color: { dark: '#1a1a1a', light: '#ffffff' } }).then((url) => {
      if (!cancelled) setDataUrl(url)
    })
    return () => {
      cancelled = true
    }
  }, [vpa, amount, payeeName, note])

  return dataUrl
}
