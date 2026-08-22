import { useEffect, useState } from 'react'
import { TopBar } from '../ui/TopBar'
import { CheckinFooter } from '../checkin/Chrome'
import { useRecordPayment, useInvoiceBooking, type InvoiceOut } from '../api/hooks'
import FindSession from './steps/FindSession'
import SessionResult from './steps/SessionResult'
import PaymentMethod from './steps/PaymentMethod'
import UpiQr from './steps/UpiQr'
import AdminOtp from './steps/AdminOtp'
import Settled from './steps/Settled'
import { useFindSession, type CheckoutBooking } from './useCheckout'

type Step = 'find' | 'session' | 'payment' | 'upi-qr' | 'admin-otp' | 'settled'
type Method = 'upi' | 'cash'

const RESEND_SECONDS = 30
const generateOtp = () => String(Math.floor(10000 + Math.random() * 90000))

const TITLES: Partial<Record<Step, string>> = {
  find: 'Checkout',
  session: 'Checkout',
  payment: 'Checkout',
  'upi-qr': 'Checkout',
  'admin-otp': 'Checkout',
}

const STEP_INDEX: Partial<Record<Step, number>> = {
  find: 1,
  session: 2,
  payment: 3,
  'upi-qr': 4,
  'admin-otp': 4,
  settled: 5,
}

export default function CheckoutFlow({ onHome }: { onHome: () => void }) {
  const [step, setStep] = useState<Step>('find')
  const [query, setQuery] = useState('')
  const [booking, setBooking] = useState<CheckoutBooking | null>(null)
  const [lookupFailed, setLookupFailed] = useState(false)
  const [method, setMethod] = useState<Method | null>(null)
  const [otp, setOtp] = useState('')
  const [otpCode, setOtpCode] = useState(generateOtp)
  const [otpError, setOtpError] = useState<string | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)
  const [settledBooking, setSettledBooking] = useState<CheckoutBooking | null>(null)
  const [invoice, setInvoice] = useState<InvoiceOut | undefined>(undefined)
  const [settleError, setSettleError] = useState<string | null>(null)

  const findSessionMutation = useFindSession()
  const recordPayment = useRecordPayment()
  const invoiceBooking = useInvoiceBooking()

  useEffect(() => {
    if (step !== 'admin-otp' || resendCooldown <= 0) return
    const t = setTimeout(() => setResendCooldown((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [step, resendCooldown])

  const findSession = async () => {
    setLookupFailed(false)
    try {
      const found = await findSessionMutation.mutateAsync(query)
      setBooking(found)
      setLookupFailed(found === null)
    } catch {
      setBooking(null)
      setLookupFailed(true)
    }
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
    setStep('find')
    setQuery('')
    setBooking(null)
    setLookupFailed(false)
    setMethod(null)
    setOtp('')
    setOtpError(null)
    setSettleError(null)
    setSettledBooking(null)
    setInvoice(undefined)
  }

  const resultStatus = findSessionMutation.isPending
    ? 'loading'
    : booking && !lookupFailed
      ? 'found'
      : 'not-found'

  const backHandlers: Record<Step, () => void> = {
    find: onHome,
    session: () => setStep('find'),
    payment: () => setStep('session'),
    'upi-qr': () => setStep('payment'),
    'admin-otp': () => setStep(method === 'upi' ? 'upi-qr' : 'payment'),
    settled: restart,
  }

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <TopBar centerTitle={TITLES[step]} onLogoClick={onHome} />

      <main className="flex min-h-0 flex-1 flex-col items-center justify-center-safe gap-8 overflow-y-auto px-4 py-[clamp(1.5rem,4vh,3rem)]">
        {step === 'find' && (
          <FindSession
            query={query}
            setQuery={setQuery}
            searching={findSessionMutation.isPending}
            onSubmit={() => void findSession()}
          />
        )}

        {step === 'session' && (
          <SessionResult
            status={resultStatus}
            booking={booking ?? undefined}
            onSettle={() => setStep('payment')}
            onRetry={() => {
              setQuery('')
              setStep('find')
            }}
            onHome={onHome}
          />
        )}

        {step === 'payment' && <PaymentMethod amount={amount} onSelect={chooseMethod} />}

        {step === 'upi-qr' && booking && (
          <UpiQr amount={amount} reference={booking.reference} onVerify={startAuthorization} />
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
