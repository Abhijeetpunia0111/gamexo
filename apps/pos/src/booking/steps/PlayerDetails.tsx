import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Draft, Customer } from '../types'
import Keyboard from '../../ui/Keyboard'
import { useIsLandscape } from '../../ui/useOrientation'

// Every vertical measurement is bounded by dvh as well as vw: landscape is short and wide,
// so width-derived padding alone makes this form taller than the space between the header
// and the footer. Sizing off the live viewport keeps the whole step on one screen.
const inputClass =
  'w-full rounded-xl border-2 border-white bg-border-input px-4 py-[clamp(0.45rem,1.4dvh,1.05rem)] text-[clamp(0.9rem,1.3vw,1.0625rem)] text-ink placeholder:text-muted focus:border-ink focus:outline-none'

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col items-start gap-[clamp(0.2rem,0.6dvh,0.375rem)]">
      <span className="flex w-full items-center justify-between text-[clamp(0.8rem,1.15vw,1rem)] font-medium text-ink">
        {label}
        {hint && <span className="text-xs font-normal text-muted">{hint}</span>}
      </span>
      {children}
    </label>
  )
}

/** Per-field cleanup applied both to typed/pasted input and to virtual-keyboard keystrokes. */
const sanitizers: Partial<Record<keyof Customer, (v: string) => string>> = {
  phone: (v) => v.replace(/\D/g, '').slice(0, 10),
  players: (v) => v.replace(/\D/g, '').slice(0, 3),
}

export default function PlayerDetails({ draft, setDraft }: { draft: Draft; setDraft: (patch: Partial<Draft>) => void }) {
  const [touched, setTouched] = useState(false)
  const [activeField, setActiveField] = useState<keyof Customer | null>(null)
  const nameRef = useRef<HTMLInputElement>(null)
  const { name, phone, email, customerId, players, notes } = draft.customer
  const phoneOk = /^\d{10}$/.test(phone)
  const isLandscape = useIsLandscape()

  // Landscape puts the app's own keyboard beside the form, so the system keyboard would
  // be a second, redundant one covering the footer — `inputMode="none"` keeps it shut.
  // Portrait has no room for a side-by-side board, so it defers to the system keyboard.
  const keys = (numeric = false) => (isLandscape ? ('none' as const) : numeric ? ('numeric' as const) : undefined)

  // Name is the first thing the counter fills in — land the cursor there (and the
  // keyboard with it) instead of making them tap in before they can type.
  useEffect(() => {
    nameRef.current?.focus()
  }, [])

  const set = (patch: Partial<Draft['customer']>) => setDraft({ customer: { ...draft.customer, ...patch } })

  // Buttons keep focus on the field they're typing into (see Keyboard's onMouseDown guard),
  // so a blur here means focus genuinely left the form — safe to hide the keyboard.
  const focusProps = (field: keyof Customer) => ({
    onFocus: () => setActiveField(field),
    onBlur: () => setActiveField((f) => (f === field ? null : f)),
  })

  const pressKey = (next: string) => {
    if (!activeField) return
    const clean = sanitizers[activeField]?.(next) ?? next
    set({ [activeField]: clean } as Partial<Draft['customer']>)
  }
  const activeValue = activeField ? draft.customer[activeField] : ''
  const pressChar = (ch: string) => pressKey(activeValue + ch)
  const pressSpace = () => pressKey(`${activeValue} `)
  const pressBackspace = () => pressKey(activeValue.slice(0, -1))

  return (
    <div className="flex w-full flex-1 flex-col items-center justify-center-safe">
      <div className="flex w-full max-w-[1160px] flex-col items-center gap-[clamp(1rem,2.5dvh,2rem)] lg:flex-row lg:items-center lg:justify-center lg:gap-[clamp(1.5rem,4vw,4.5rem)]">
        <div className="flex w-full flex-col gap-[clamp(0.5rem,1.6dvh,1.25rem)] lg:max-w-[480px]">
          <p className="text-[clamp(1.05rem,1.8vw,1.5rem)] font-semibold text-ink">Who&apos;s playing?</p>

          <div className="flex w-full flex-col gap-[clamp(0.4rem,1.3dvh,1rem)]">
            <Field label="Phone number">
              <div className="relative w-full">
                <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[clamp(0.9rem,1.3vw,1.0625rem)] text-muted">
                  +91
                </span>
                <input
                  className={`${inputClass} pl-12`}
                  inputMode={keys(true)}
                  autoComplete="tel"
                  maxLength={10}
                  placeholder="90000 00000"
                  value={phone}
                  onChange={(e) => set({ phone: e.target.value.replace(/\D/g, '').slice(0, 10) })}
                  {...focusProps('phone')}
                  onBlur={() => {
                    setTouched(true)
                    setActiveField((f) => (f === 'phone' ? null : f))
                  }}
                />
              </div>
              {touched && phone && !phoneOk && <p className="text-xs text-negative">Enter all 10 digits.</p>}
            </Field>

            <Field label="Name">
              <input
                ref={nameRef}
                className={inputClass}
                inputMode={keys()}
                autoComplete="name"
                placeholder="Player's name"
                value={name}
                onChange={(e) => set({ name: e.target.value })}
                {...focusProps('name')}
              />
            </Field>

            <div className="grid gap-[clamp(0.4rem,1.3dvh,1rem)] sm:grid-cols-2">
              <Field label="Players">
                <input
                  className={inputClass}
                  inputMode={keys(true)}
                  placeholder="How many"
                  value={players}
                  onChange={(e) => set({ players: e.target.value.replace(/\D/g, '').slice(0, 3) })}
                  {...focusProps('players')}
                />
              </Field>
              <Field label="Email" hint="Optional">
                <input
                  className={inputClass}
                  type="email"
                  inputMode={keys()}
                  autoComplete="email"
                  placeholder="For the invoice"
                  value={email}
                  onChange={(e) => set({ email: e.target.value })}
                  {...focusProps('email')}
                />
              </Field>
            </div>

            <Field label="Membership ID" hint="Optional">
              <input
                className={inputClass}
                inputMode={keys()}
                placeholder="Only for existing members"
                value={customerId}
                onChange={(e) => set({ customerId: e.target.value })}
                {...focusProps('customerId')}
              />
            </Field>

            <Field label="Anything we should know" hint="Optional">
              <textarea
                className={`${inputClass} min-h-[clamp(2.5rem,7dvh,4.75rem)] resize-none`}
                inputMode={keys()}
                placeholder="Bringing a coach, need extra lights…"
                value={notes}
                onChange={(e) => set({ notes: e.target.value })}
                {...focusProps('notes')}
              />
            </Field>
          </div>
        </div>

        {/* Landscape only. In portrait the form already fills the width, leaving nowhere to
            put a board beside it — the system keyboard handles typing there instead. */}
        {isLandscape && activeField && (
          <div className="w-auto max-w-[560px] shrink-0">
            <Keyboard onChar={pressChar} onSpace={pressSpace} onBackspace={pressBackspace} />
          </div>
        )}
      </div>
    </div>
  )
}
