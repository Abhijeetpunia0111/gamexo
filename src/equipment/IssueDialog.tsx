import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { money, type Equipment } from '../data/booking'
import * as db from '../lib/db'

const inputClass =
  'w-full rounded-lg border border-border-input bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-muted focus:border-ink focus:outline-none'

function defaultDueBack() {
  const d = new Date(Date.now() + 3 * 3600_000)
  return d.toISOString().slice(0, 16)
}

export default function IssueDialog({ item, onClose }: { item: Equipment; onClose: () => void }) {
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [qty, setQty] = useState(1)
  const [dueBack, setDueBack] = useState(defaultDueBack)

  const phoneOk = /^\d{10}$/.test(phone)
  const adjustments = db.getStockAdjustments()
  const available = item.stock + (adjustments[item.id] || 0)

  useEffect(() => {
    if (!phoneOk) return
    const match = db.findCustomer(phone)
    if (match) setName(match.name)
  }, [phone, phoneOk])

  const ready = phoneOk && name.trim().length > 1 && qty > 0 && qty <= available

  const issue = () => {
    db.issueRental({
      itemId: item.id,
      qty,
      deposit: (item.deposit || 0) * qty,
      customer: { name: name.trim(), phone },
      issuedAt: new Date().toISOString(),
      dueBackAt: new Date(dueBack).toISOString(),
    })
    db.upsertCustomer({ name: name.trim(), phone })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="flex w-full max-w-[420px] flex-col gap-4 rounded-2xl bg-white p-6">
        <div className="flex items-center justify-between">
          <p className="text-lg font-semibold text-ink">Issue {item.name}</p>
          <button type="button" onClick={onClose} aria-label="Close" className="text-muted hover:text-ink">
            <X size={20} />
          </button>
        </div>
        <p className="text-xs text-muted">{available} available on the shelf right now</p>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-slate">Phone number</span>
          <div className="relative">
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-muted">+91</span>
            <input
              className={`${inputClass} pl-11`}
              inputMode="numeric"
              maxLength={10}
              placeholder="90000 00000"
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
            />
          </div>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-slate">Name</span>
          <input className={inputClass} placeholder="Who's taking it" value={name} onChange={(e) => setName(e.target.value)} />
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate">Quantity</span>
            <input
              type="number"
              min={1}
              max={available}
              className={inputClass}
              value={qty}
              onChange={(e) => setQty(Math.max(1, Math.min(available, Number(e.target.value) || 1)))}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate">Due back</span>
            <input type="datetime-local" className={inputClass} value={dueBack} onChange={(e) => setDueBack(e.target.value)} />
          </label>
        </div>

        {item.deposit ? (
          <div className="flex items-center justify-between rounded-lg bg-surface-muted px-3.5 py-2.5 text-sm">
            <span className="text-slate">Deposit to collect</span>
            <span className="font-medium text-ink">{money(item.deposit * qty)}</span>
          </div>
        ) : null}

        <button
          type="button"
          disabled={!ready}
          onClick={issue}
          className="flex h-11 items-center justify-center rounded-full text-sm text-[#fefefe] disabled:opacity-40"
          style={{ backgroundImage: 'linear-gradient(105deg, rgb(41,41,41) 2%, rgb(26,26,26) 100%)' }}
        >
          Issue {qty > 1 ? `${qty} items` : 'item'}
        </button>
      </div>
    </div>
  )
}
