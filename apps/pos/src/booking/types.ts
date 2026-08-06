export type Customer = {
  name: string
  phone: string
  email: string
  /** Optional membership/loyalty ID for a returning player — not required to book. */
  customerId: string
  players: string
  notes: string
}

export type Draft = {
  sportId: string | null
  courtId: string | null
  date: string | null
  startHour: number | null
  hours: number
  customer: Customer
  /** equipmentId -> qty */
  equipment: Record<string, number>
  paymentMethod: 'cash' | 'upi' | 'card' | 'bank' | 'cheque'
  /** true = charge now, false = check the player in and collect at checkout. */
  payNow: boolean
}

export const emptyCustomer = (): Customer => ({
  name: '',
  phone: '',
  email: '',
  customerId: '',
  players: '',
  notes: '',
})

export const emptyDraft = (): Draft => ({
  sportId: null,
  courtId: null,
  date: null,
  startHour: null,
  hours: 1,
  customer: emptyCustomer(),
  equipment: {},
  paymentMethod: 'cash',
  payNow: false,
})
