import { useState, type ReactNode } from 'react'
import type { Draft } from '../types'

const inputClass =
  'w-full rounded-xl border-2 border-white bg-border-input px-3.5 py-3 text-[15px] text-ink shadow-[0px_12px_17px_-9px_rgba(0,0,0,0.12)] placeholder:text-muted focus:border-ink focus:outline-none'

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col items-start gap-1.5">
      <span className="flex w-full items-center justify-between text-sm font-medium text-ink">
        {label}
        {hint && <span className="text-xs font-normal text-muted">{hint}</span>}
      </span>
      {children}
    </label>
  )
}

export default function PlayerDetails({ draft, setDraft }: { draft: Draft; setDraft: (patch: Partial<Draft>) => void }) {
  const [touched, setTouched] = useState(false)
  const { name, phone, email, customerId, players, notes } = draft.customer
  const phoneOk = /^\d{10}$/.test(phone)

  const set = (patch: Partial<Draft['customer']>) => setDraft({ customer: { ...draft.customer, ...patch } })

  return (
    <div className="flex w-full flex-col gap-5">
      <p className="text-[clamp(1rem,1.3vw,1.125rem)] font-medium text-ink">Who&apos;s playing?</p>

      <div className="flex w-full flex-col gap-4 rounded-2xl bg-surface p-[clamp(1.1rem,2vw,1.5rem)] sm:max-w-[520px]">
        <Field label="Phone number">
          <div className="relative w-full">
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[15px] text-muted">+91</span>
            <input
              className={`${inputClass} pl-11`}
              inputMode="numeric"
              autoComplete="tel"
              maxLength={10}
              placeholder="90000 00000"
              value={phone}
              onChange={(e) => set({ phone: e.target.value.replace(/\D/g, '').slice(0, 10) })}
              onBlur={() => setTouched(true)}
            />
          </div>
          {touched && phone && !phoneOk && <p className="text-xs text-negative">Enter all 10 digits.</p>}
        </Field>

        <Field label="Name">
          <input
            className={inputClass}
            autoComplete="name"
            placeholder="Player's name"
            value={name}
            onChange={(e) => set({ name: e.target.value })}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Players">
            <input
              className={inputClass}
              inputMode="numeric"
              placeholder="How many"
              value={players}
              onChange={(e) => set({ players: e.target.value.replace(/\D/g, '').slice(0, 3) })}
            />
          </Field>
          <Field label="Email" hint="Optional">
            <input
              className={inputClass}
              type="email"
              autoComplete="email"
              placeholder="For the invoice"
              value={email}
              onChange={(e) => set({ email: e.target.value })}
            />
          </Field>
        </div>

        <Field label="Membership ID" hint="Optional">
          <input
            className={inputClass}
            placeholder="Only for existing members"
            value={customerId}
            onChange={(e) => set({ customerId: e.target.value })}
          />
        </Field>

        <Field label="Anything we should know" hint="Optional">
          <textarea
            className={`${inputClass} min-h-[76px] resize-none`}
            placeholder="Bringing a coach, need extra lights…"
            value={notes}
            onChange={(e) => set({ notes: e.target.value })}
          />
        </Field>
      </div>
    </div>
  )
}
