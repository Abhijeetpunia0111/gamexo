import { useEffect, useState } from 'react'
import { TopBar } from '../ui/TopBar'
import { CheckinFooter } from './Chrome'
import ChooseMethod from './steps/ChooseMethod'
import EnterNumber from './steps/EnterNumber'
import VerifyOtp from './steps/VerifyOtp'
import CheckInResult from './steps/CheckInResult'
import { useFindBookingByPhone } from './useCheckIn'
import { DEFAULT_COUNTRY } from './countries'

type Step = 'method' | 'phone' | 'otp' | 'result'

const RESEND_SECONDS = 30
const generateOtp = () => String(Math.floor(10000 + Math.random() * 90000))

const TITLES: Partial<Record<Step, string>> = {
  method: 'Check In',
  phone: 'Confirm Check In',
  otp: 'Confirm Check In',
}

const STEP_INDEX: Partial<Record<Step, number>> = { phone: 1, otp: 2, result: 3 }

export default function CheckInFlow({
  onHome,
  onBookNow,
  onStore,
}: {
  onHome: () => void
  onBookNow: () => void
  onStore: () => void
}) {
  const [step, setStep] = useState<Step>('method')
  const [phone, setPhone] = useState('')
  const [country, setCountry] = useState(DEFAULT_COUNTRY)
  const [otp, setOtp] = useState('')
  const [otpCode, setOtpCode] = useState(generateOtp)
  const [otpError, setOtpError] = useState<string | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)
  const [verifiedPhone, setVerifiedPhone] = useState<string | null>(null)

  const bookingQuery = useFindBookingByPhone(verifiedPhone)

  useEffect(() => {
    if (step !== 'otp' || resendCooldown <= 0) return
    const t = setTimeout(() => setResendCooldown((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [step, resendCooldown])

  const goPhone = () => {
    setOtpError(null)
    setStep('phone')
  }

  const sendOtp = () => {
    setOtpCode(generateOtp())
    setOtp('')
    setOtpError(null)
    setResendCooldown(RESEND_SECONDS)
    setStep('otp')
  }

  const resendOtp = () => {
    if (resendCooldown > 0) return
    setOtpCode(generateOtp())
    setOtp('')
    setOtpError(null)
    setResendCooldown(RESEND_SECONDS)
  }

  const verifyOtp = () => {
    setVerifying(true)
    setOtpError(null)
    // Mimics a real verify round-trip — there's no SMS backend behind this yet, so the
    // check itself is just a string compare against the code shown in the dev hint.
    setTimeout(() => {
      setVerifying(false)
      if (otp === otpCode) {
        setVerifiedPhone(phone)
        setStep('result')
      } else {
        setOtpError('That code doesn’t match — try again.')
        setOtp('')
      }
    }, 500)
  }

  const restart = () => {
    setStep('method')
    setPhone('')
    setOtp('')
    setOtpError(null)
    setVerifiedPhone(null)
  }

  const resultStatus = bookingQuery.isPending ? 'loading' : bookingQuery.data ? 'found' : 'not-found'

  const backHandlers: Record<Step, () => void> = {
    method: onHome,
    phone: () => setStep('method'),
    otp: goPhone,
    result: restart,
  }

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto">
      <TopBar centerTitle={TITLES[step]} onLogoClick={onHome} />

      <main className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-[clamp(1.5rem,4vh,3rem)]">
        {step === 'method' && <ChooseMethod onHaveBooking={goPhone} onBookNow={onBookNow} />}

        {step === 'phone' && (
          <EnterNumber phone={phone} setPhone={setPhone} country={country} setCountry={setCountry} onSubmit={sendOtp} />
        )}

        {step === 'otp' && (
          <VerifyOtp
            phone={phone}
            country={country}
            otp={otp}
            setOtp={setOtp}
            demoCode={otpCode}
            error={otpError}
            verifying={verifying}
            resendCooldown={resendCooldown}
            onVerify={verifyOtp}
            onResend={resendOtp}
          />
        )}

        {step === 'result' && (
          <CheckInResult
            status={resultStatus}
            booking={bookingQuery.data}
            onRentEquipment={onStore}
            onHome={onHome}
            onRetry={goPhone}
            onBookNow={onBookNow}
          />
        )}
      </main>

      <CheckinFooter
        onBack={backHandlers[step]}
        onHome={step === 'result' ? undefined : onHome}
        step={STEP_INDEX[step]}
        totalSteps={STEP_INDEX[step] ? 3 : undefined}
      />
    </div>
  )
}
