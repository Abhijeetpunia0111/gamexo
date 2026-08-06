import { useEffect, useMemo } from 'react'
import { useCourts, useCourtAvailability, type Slot } from '../../api/hooks'
import { hour12, money, nextDays, slotChipLabel, toISO } from '../../lib/format'
import type { Draft } from '../types'

const GROUPS = [
  { id: 'morning', label: 'Morning', from: 6, to: 12 },
  { id: 'afternoon', label: 'Afternoon', from: 12, to: 17 },
  { id: 'evening', label: 'Evening', from: 17, to: 24 },
]

type HourState = 'open' | 'booked' | 'past'

/** Real slots (from GET /courts/availability) collapsed to one entry per local hour —
 *  the grid is hourly even though the API can return finer granularity. */
function toHourly(slots: Slot[]) {
  const byHour = new Map<number, HourState>()
  const now = new Date()
  for (const slot of slots) {
    const start = new Date(slot.starts_at)
    const hour = start.getHours()
    const state: HourState = start < now ? 'past' : slot.available ? 'open' : 'booked'
    // A hard "past"/"booked" beats "open" if the slot repeats across granularities.
    const existing = byHour.get(hour)
    if (!existing || existing === 'open') byHour.set(hour, state)
  }
  return byHour
}

export default function DateTime({ draft, setDraft }: { draft: Draft; setDraft: (patch: Partial<Draft>) => void }) {
  const courtsQuery = useCourts(draft.sportId || undefined)
  const court = courtsQuery.data?.find((c) => c.id === draft.courtId)
  const days = useMemo(() => nextDays(7), [])
  const date = draft.date || toISO(new Date())

  const availability = useCourtAvailability(draft.courtId || undefined, date, 60)
  const hourly = useMemo(() => toHourly(availability.data ?? []), [availability.data])

  const maxHours = useMemo(() => {
    if (draft.startHour == null) return 1
    let n = 0
    while (n < 3 && hourly.get(draft.startHour + n) === 'open') n++
    return Math.max(1, n)
  }, [draft.startHour, hourly])

  // Walk-in default: as soon as a day's slots load with nothing picked yet, jump to the
  // soonest open hour so staff can go straight to player details. Still fully editable below.
  useEffect(() => {
    if (draft.startHour != null || availability.isPending) return
    const openHours = [...hourly.entries()]
      .filter(([, state]) => state === 'open')
      .map(([hour]) => hour)
      .sort((a, b) => a - b)
    // `date` must land in the draft here too — otherwise a walk-in that never taps a day
    // chip keeps draft.date null, and the payment step's quote (which needs both) never fires.
    if (openHours.length > 0) setDraft({ date, startHour: openHours[0], hours: 1 })
  }, [availability.isPending, hourly, draft.startHour, date, setDraft])

  const selected = (hour: number) =>
    draft.startHour != null && hour >= draft.startHour && hour < draft.startHour + draft.hours

  const slotTotal = (court?.price || 0) * draft.hours

  return (
    <div className="flex w-full flex-col gap-5">
      <div className="flex w-full items-center justify-between">
        <p className="text-[clamp(1rem,1.3vw,1.125rem)] font-medium text-ink">When&apos;s the walk-in playing?</p>
        <p className="text-[clamp(0.875rem,1vw,0.9375rem)] text-muted">
          {court?.name} · <span className="font-semibold text-positive">{money(court?.price || 0)}/hr</span>
        </p>
      </div>

      <div className="flex w-full gap-2 overflow-x-auto rounded-2xl bg-surface p-[clamp(0.625rem,1.2vw,0.875rem)]">
        {days.map((d) => {
          const active = date === d.iso
          return (
            <button
              key={d.iso}
              type="button"
              onClick={() => setDraft({ date: d.iso, startHour: null })}
              className={`flex min-w-[clamp(3.75rem,7vw,4.5rem)] shrink-0 flex-col items-center gap-1 rounded-xl px-3 py-[clamp(0.625rem,1.2vw,0.875rem)] transition-colors ${
                active ? 'bg-ink text-white' : 'bg-surface-muted text-ink hover:bg-border-input'
              }`}
            >
              <span className={`text-[11px] font-medium ${active ? 'text-white/60' : 'text-muted'}`}>{d.label}</span>
              <span className="text-[clamp(1rem,1.4vw,1.0625rem)] font-bold leading-none">{d.dayNum}</span>
              <span className={`text-[10px] font-medium uppercase tracking-wide ${active ? 'text-white/50' : 'text-muted'}`}>
                {d.monthShort}
              </span>
            </button>
          )
        })}
      </div>

      <div className="flex w-full flex-col gap-5 rounded-2xl bg-surface p-[clamp(1rem,2vw,1.375rem)]">
        {availability.isPending ? (
          <p className="text-sm text-muted">Checking real-time availability…</p>
        ) : availability.error ? (
          <p role="alert" className="text-sm text-negative">
            Could not load availability: {availability.error instanceof Error ? availability.error.message : 'unknown error'}
          </p>
        ) : (
          GROUPS.map((group) => {
            const hours = Array.from({ length: group.to - group.from }, (_, i) => group.from + i)
            const free = hours.filter((h) => hourly.get(h) === 'open').length
            return (
              <section key={group.id}>
                <div className="mb-2.5 flex items-baseline justify-between">
                  <p className="text-[clamp(0.8125rem,0.95vw,0.875rem)] font-semibold uppercase tracking-wide text-muted">
                    {group.label}
                  </p>
                  <span className="text-[11px] text-muted">{free} free</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {hours.map((hour) => {
                    const state = hourly.get(hour) ?? 'past'
                    const isSelected = selected(hour)
                    const disabled = state !== 'open' && !isSelected
                    return (
                      <button
                        key={hour}
                        type="button"
                        disabled={disabled}
                        onClick={() => setDraft({ startHour: hour, hours: 1 })}
                        className={`rounded-xl px-3.5 py-2 text-[clamp(0.875rem,1vw,0.9375rem)] font-medium transition-colors ${
                          isSelected
                            ? 'bg-ink text-white'
                            : state === 'open'
                              ? 'bg-white text-ink hover:bg-border-input'
                              : 'cursor-not-allowed bg-white text-muted line-through'
                        }`}
                      >
                        {slotChipLabel(hour)}
                      </button>
                    )
                  })}
                </div>
              </section>
            )
          })
        )}
      </div>

      {draft.startHour != null && (
        <div className="flex w-full flex-col gap-3 rounded-2xl bg-surface p-[clamp(1rem,2vw,1.375rem)]">
          <div className="flex items-baseline justify-between">
            <div>
              <p className="text-[clamp(0.8125rem,0.95vw,0.875rem)] font-semibold uppercase tracking-wide text-muted">
                Your slot
              </p>
              <p className="mt-1 text-[clamp(1rem,1.3vw,1.125rem)] font-semibold text-ink">
                {hour12(draft.startHour)} – {hour12(draft.startHour + draft.hours)}
              </p>
            </div>
            <p className="text-[clamp(1.375rem,2vw,1.5rem)] font-bold leading-none text-ink">{money(slotTotal)}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[13px] text-muted">Play for</span>
            {[1, 2, 3].map((h) => {
              const active = draft.hours === h
              const allowed = h <= maxHours
              return (
                <button
                  key={h}
                  type="button"
                  disabled={!allowed}
                  onClick={() => setDraft({ hours: h })}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? 'bg-ink text-white'
                      : allowed
                        ? 'bg-white text-ink hover:bg-border-input'
                        : 'cursor-not-allowed bg-white text-muted'
                  }`}
                >
                  {h} hr
                </button>
              )
            })}
          </div>
          {maxHours < 3 && (
            <p className="text-[12px] text-muted">
              The next hour is taken, so this slot runs up to {maxHours} hour{maxHours > 1 ? 's' : ''}.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
