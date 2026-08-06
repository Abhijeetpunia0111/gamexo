import { useEffect, useState } from 'react'
import { Banknote, CreditCard, QrCode } from 'lucide-react'
import { money } from '../../lib/format'

const METHODS = [
  { id: 'upi' as const, label: 'UPI', hint: 'Scan & pay — GPay, PhonePe, Paytm', icon: QrCode },
  { id: 'cash' as const, label: 'Cash', hint: 'Collect at the counter', icon: Banknote },
  { id: 'card' as const, label: 'Card', hint: 'Credit / debit card', icon: CreditCard },
]

export default function PaymentMethod({
  amount,
  onSelect,
}: {
  amount: number
  onSelect: (method: 'upi' | 'cash') => void
}) {
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 2500)
    return () => clearTimeout(t)
  }, [toast])

  return (
    <div className="flex w-full max-w-[520px] flex-col items-center gap-[clamp(1.75rem,4vw,3rem)]">
      <div className="flex flex-col items-center gap-1 text-center">
        <p className="font-display text-[clamp(1.15rem,1.9vw,1.5rem)] font-bold text-ink">Choose payment method</p>
        <p className="text-[clamp(0.9375rem,1.1vw,1rem)] text-muted">Settling {money(amount)}</p>
      </div>

      <div className="flex w-full flex-col gap-3">
        {METHODS.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => (m.id === 'card' ? setToast('Card payments are coming soon') : onSelect(m.id))}
            className="flex items-center gap-4 rounded-2xl bg-surface px-[clamp(1.25rem,2vw,1.5rem)] py-[clamp(1.1rem,1.8vw,1.375rem)] text-left transition-transform hover:-translate-y-0.5"
          >
            <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-surface-muted text-ink">
              <m.icon size={22} strokeWidth={1.75} />
            </span>
            <span className="flex flex-col gap-0.5">
              <span className="text-[clamp(1rem,1.4vw,1.125rem)] font-bold text-ink">{m.label}</span>
              <span className="text-[clamp(0.8125rem,1vw,0.875rem)] text-muted">{m.hint}</span>
            </span>
          </button>
        ))}
      </div>

      {toast && (
        <div className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-xl bg-ink px-4 py-2.5 text-sm font-medium text-white shadow-[0px_12px_24px_-8px_rgba(0,0,0,0.35)]">
          {toast}
        </div>
      )}
    </div>
  )
}
