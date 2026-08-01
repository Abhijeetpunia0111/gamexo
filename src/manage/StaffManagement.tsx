import { useState } from 'react'
import * as db from '../lib/db'
import type { StaffRole } from '../lib/db'

const ROLES: StaffRole[] = ['admin', 'staff', 'coach']

const roleTone = (role: StaffRole) =>
  role === 'admin'
    ? 'bg-ink text-white'
    : role === 'coach'
      ? 'bg-lime/25 text-lime-ink'
      : 'bg-surface-muted text-slate'

export default function StaffManagement() {
  db.useDbVersion()
  const staff = db.getStaff()

  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [role, setRole] = useState<StaffRole>('staff')

  const canAdd = name.trim().length > 1 && /^\d{10}$/.test(phone)

  const add = () => {
    if (!canAdd) return
    db.saveStaffMember({ id: `ST${Date.now()}`, name: name.trim(), phone, role })
    setName('')
    setPhone('')
    setRole('staff')
  }

  return (
    <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-4 py-5 sm:px-6">
      <p className="text-lg text-ink">Manage Staff</p>

      <div className="flex w-full flex-col gap-3 rounded-2xl border border-border-card bg-white p-5 shadow-[0px_5px_13px_0px_rgba(0,0,0,0.05)] sm:flex-row sm:items-end">
        <label className="flex flex-1 flex-col gap-1.5 text-sm">
          <span className="text-slate">Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Full name"
            className="rounded-lg border border-border-input bg-surface px-3 py-2.5 text-ink outline-none focus:border-ink"
          />
        </label>
        <label className="flex flex-1 flex-col gap-1.5 text-sm">
          <span className="text-slate">Phone</span>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
            placeholder="10-digit number"
            inputMode="numeric"
            className="rounded-lg border border-border-input bg-surface px-3 py-2.5 text-ink outline-none focus:border-ink"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm sm:w-40">
          <span className="text-slate">Role</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as StaffRole)}
            className="rounded-lg border border-border-input bg-surface px-3 py-2.5 capitalize text-ink outline-none focus:border-ink"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={!canAdd}
          onClick={add}
          className="h-[42px] shrink-0 rounded-lg bg-ink px-5 text-sm font-medium text-white disabled:opacity-40"
        >
          Add staff
        </button>
      </div>

      <div className="w-full overflow-hidden rounded-2xl border border-border-card bg-white shadow-[0px_5px_13px_0px_rgba(0,0,0,0.05)]">
        {staff.map((member, i) => (
          <div
            key={member.id}
            className={`flex items-center justify-between gap-3 px-5 py-3.5 ${
              i < staff.length - 1 ? 'border-b border-border-card' : ''
            }`}
          >
            <div>
              <p className="text-sm font-semibold text-ink">{member.name}</p>
              <p className="text-xs text-muted">
                {member.phone}
                {member.specialty ? ` · ${member.specialty}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${roleTone(member.role)}`}>
                {member.role}
              </span>
              <select
                value={member.role}
                onChange={(e) => db.setStaffRole(member.id, e.target.value as StaffRole)}
                className="rounded-lg border border-border-input bg-surface px-2.5 py-1.5 text-xs font-medium capitalize text-ink"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
