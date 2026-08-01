import * as db from '../lib/db'
import { MEMBERSHIP_TIERS, tierForVisits } from './membershipTier'

export default function Membership() {
  db.useDbVersion()
  const customers = db.getCustomers()

  return (
    <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-4 py-5 sm:px-6">
      <p className="text-lg text-ink">Membership Tiers</p>
      <p className="-mt-3 text-sm text-slate">Tiers are earned automatically from a customer's visit count.</p>

      <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {MEMBERSHIP_TIERS.map((tier) => {
          const count = customers.filter((c) => tierForVisits(c.visits) === tier.name).length
          return (
            <div
              key={tier.name}
              className="flex flex-col gap-2 rounded-xl border border-border-card bg-white p-4 shadow-[0px_5px_13px_0px_rgba(0,0,0,0.05)]"
            >
              <p className="text-sm font-semibold text-ink">{tier.name}</p>
              <p className="text-xs text-muted">{tier.minVisits}+ visits</p>
              <p className="text-xs text-slate">{tier.perk}</p>
              <p className="mt-2 text-2xl font-semibold text-ink">{count}</p>
              <p className="text-xs text-muted">members</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
