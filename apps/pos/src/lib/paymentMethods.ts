export type PaymentMethodId = 'cash' | 'upi' | 'card' | 'bank' | 'cheque'

export const PAYMENT_METHODS: { id: PaymentMethodId; name: string; hint: string }[] = [
  { id: 'upi', name: 'UPI', hint: 'GPay, PhonePe, Paytm' },
  { id: 'card', name: 'Card', hint: 'Visa, Mastercard, RuPay' },
  { id: 'cash', name: 'Cash', hint: 'Collect at the counter' },
  { id: 'bank', name: 'Bank transfer', hint: 'NEFT / IMPS' },
  { id: 'cheque', name: 'Cheque', hint: 'Rarely used' },
]
