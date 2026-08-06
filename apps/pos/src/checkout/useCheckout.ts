import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import QRCode from 'qrcode'
import { api } from '../api/client'
import type { components } from '../api/schema'

export type CheckoutBooking = components['schemas']['BookingDetail']

/** Finds the walk-in's current session by phone for the settle-bill flow. Goes by the
 *  actual clock rather than the `status` enum — nothing here flips a booking from
 *  "upcoming" to "active"/"completed" as its slot passes, so a booking whose start time
 *  has already come is "checked in" regardless of what its stored status still says. */
export function useActiveSessionByPhone(phone: string | null) {
  return useQuery({
    queryKey: ['checkout-active-session', phone],
    queryFn: async () => {
      const res = await api.listBookings({ search: phone!, size: 15 })
      const now = Date.now()
      const live = (res.items ?? []).filter(
        (b) => b.status !== 'cancelled' && new Date(b.starts_at).getTime() <= now,
      )
      if (live.length === 0) return null
      live.sort((a, b) => new Date(b.starts_at).getTime() - new Date(a.starts_at).getTime())
      return api.getBooking(live[0].id)
    },
    enabled: !!phone,
    retry: false,
    staleTime: 0,
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
