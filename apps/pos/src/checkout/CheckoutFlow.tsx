import { useEffect, useState } from 'react'
import { TopBar } from '../ui/TopBar'
import { CheckinFooter } from '../checkin/Chrome'
import { useRecordPayment, useInvoiceBooking, type InvoiceOut } from '../api/hooks'
import EnterNumber from './steps/EnterNumber'
import SessionResult from './steps/SessionResult'
import PaymentMethod from './steps/PaymentMethod'
import UpiQr from './steps/UpiQr'
import AdminOtp from './steps/AdminOtp'
import Settled from './steps/Settled'
import { useActiveSessionByPhone, type CheckoutBooking } from './useCheckout'

type Step = 'phone' | 'session' | 'payment' | 'upi-qr' | 'admin-otp' | 'settled'
type Method = 'upi' | 'cash'

const RESEND_SECONDS = 30
const generateOtp = () => String(Math.floor(10000 + Math.random() * 90000))

const TITLES: Partial<Record<Step, string>> = {
  phone: 'Checkout',
  session: 'Checkout',
  payment: 'Checkout',
  'upi-qr': 'Checkout',
  'admin-otp': 'Checkout',
}

const STEP_INDEX: Partial<Record<Step, number>> = {
  phone: 1,
  session: 2,
  payment: 3,
  'upi-qr': 4,
  'admin-otp': 4,
  settled: 5,
}

export default function CheckoutFlow({ onHome }: { onHome: () => void }) {
  const [step, setStep] = useState<Step>('phone')
  const [phone, setPhone] = useState('')
  const [searchPhone, setSearchPhone] = useState<string | null>(null)
  const [method, setMethod] = useState<Method | null>(null)
  const [otp, setOtp] = useState('')
  const [otpCode, setOtpCode] = useState(generateOtp)
  const [otpError, setOtpError] = useState<string | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)
  const [settledBooking, setSettledBooking] = useState<CheckoutBooking | null>(null)
  const [invoice, setInvoice] = useState<InvoiceOut | undefined>(undefined)
  const [settleError, setSettleError] = useState<string | null>(null)

  const sessionQuery = useActiveSessionByPhone(searchPhone)
  const recordPayment = useRecordPayment()
  const invoiceBooking = useInvoiceBooking()

  useEffect(() => {
    if (step !== 'admin-otp' || resendCooldown <= 0) return
    const t = setTimeout(() => setResendCooldown((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [step, resendCooldown])

  const findSession = () => {
    setSearchPhone(phone)
    setStep('session')
  }

  const startAuthorization = () => {
    setOtpCode(generateOtp())
    setOtp('')
    setOtpError(null)
    setResendCooldown(RESEND_SECONDS)
    setStep('admin-otp')
  }

  const chooseMethod = (m: Method) => {
    setMethod(m)
    setStep(m === 'upi' ? 'upi-qr' : 'admin-otp')
    if (m === 'cash') startAuthorization()
  }

  const resendOtp = () => {
    if (resendCooldown > 0) return
    setOtpCode(generateOtp())
    setOtp('')
    setOtpError(null)
    setResendCooldown(RESEND_SECONDS)
  }

  const booking = sessionQuery.data
  const amount = booking ? Number(booking.balance_due) : 0
  const alreadySettled = step === 'session' && !!booking && amount <= 0

  const verifyAndSettle = () => {
    if (!booking || !method) return
    setVerifying(true)
    setOtpError(null)
    setSettleError(null)
    // Mirrors the check-in OTP mock — no admin-PIN backend exists yet, so the check
    // itself is a string compare against the code shown in the dev hint.
    setTimeout(async () => {
      if (otp !== otpCode) {
        setVerifying(false)
        setOtpError('That code doesn’t match — try again.')
        setOtp('')
        return
      }
      try {
        await recordPayment.mutateAsync({ bookingId: booking.id, amount, method })
        let inv: InvoiceOut | undefined
        try {
          inv = await invoiceBooking.mutateAsync(booking.id)
        } catch {
          inv = undefined
        }
        setSettledBooking(booking)
        setInvoice(inv)
        setVerifying(false)
        setStep('settled')
      } catch (err) {
        setVerifying(false)
        setSettleError(err instanceof Error ? err.message : 'Could not record the payment. Try again.')
      }
    }, 500)
  }

  const restart = () => {
    setStep('phone')
    setPhone('')
    setSearchPhone(null)
    setMethod(null)
    setOtp('')
    setOtpError(null)
    setSettleError(null)
    setSettledBooking(null)
    setInvoice(undefined)
  }

  const resultStatus = sessionQuery.isPending ? 'loading' : sessionQuery.data ? 'found' : 'not-found'

  const backHandlers: Record<Step, () => void> = {
    phone: onHome,
    session: () => setStep('phone'),
    payment: () => setStep('session'),
    'upi-qr': () => setStep('payment'),
    'admin-otp': () => setStep(method === 'upi' ? 'upi-qr' : 'payment'),
    settled: restart,
  }

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto">
      <TopBar centerTitle={TITLES[step]} onLogoClick={onHome} />

      <main className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-[clamp(1.5rem,4vh,3rem)]">
        {step === 'phone' && <EnterNumber phone={phone} setPhone={setPhone} onSubmit={findSession} />}

        {step === 'session' && (
          <SessionResult
            status={resultStatus}
            booking={booking}
            onSettle={() => setStep('payment')}
            onRetry={() => setStep('phone')}
            onHome={onHome}
          />
        )}

        {step === 'payment' && <PaymentMethod amount={amount} onSelect={chooseMethod} />}

        {step === 'upi-qr' && booking && (
          <UpiQr amount={amount} reference={`BK-${booking.id.slice(0, 8).toUpperCase()}`} onVerify={startAuthorization} />
        )}

        {step === 'admin-otp' && (
          <div className="flex w-full flex-col items-center gap-3">
            <AdminOtp
              otp={otp}
              setOtp={setOtp}
              demoCode={otpCode}
              error={otpError}
              verifying={verifying}
              resendCooldown={resendCooldown}
              onVerify={verifyAndSettle}
              onResend={resendOtp}
            />
            {settleError && (
              <p role="alert" className="text-sm text-negative">
                {settleError}
              </p>
            )}
          </div>
        )}

        {step === 'settled' && settledBooking && method && (
          <Settled booking={settledBooking} invoice={invoice} amount={amount} method={method} onHome={onHome} />
        )}
      </main>

      <CheckinFooter
        onBack={backHandlers[step]}
        onHome={step === 'settled' ? undefined : onHome}
        step={alreadySettled ? undefined : STEP_INDEX[step]}
        totalSteps={alreadySettled ? undefined : STEP_INDEX[step] ? 5 : undefined}
      />
    </div>
  )
}
