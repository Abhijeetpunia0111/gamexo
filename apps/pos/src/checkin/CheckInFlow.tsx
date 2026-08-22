import { useState } from 'react'
import { TopBar } from '../ui/TopBar'
import { CheckinFooter } from './Chrome'
import ChooseMethod from './steps/ChooseMethod'
import EnterBookingId from './steps/EnterBookingId'
import CheckInResult from './steps/CheckInResult'
import { lookupErrorMessage, useLookupBooking, type CheckinBooking } from './useCheckIn'

/**
 * Check in against the reference on the customer's ticket.
 *
 * Was: phone number → OTP → search every booking for that number → rank the matches
 * to guess which one they meant. Four screens and an SMS to identify something the
 * customer was already holding. Now the Booking ID identifies exactly one booking,
 * so there is nothing to disambiguate and nothing to wait for.
 *
 * The OTP is gone with it. It verified the phone, not the booking, and the code was
 * never sent anywhere — it was a string compare against a number printed on screen.
 * Knowing a reference that was mailed privately is the proof, and the worst case is
 * someone checking in to a court they did not pay for, which the desk sees.
 */
type Step = 'method' | 'reference' | 'result'

const TITLES: Partial<Record<Step, string>> = {
  method: 'Check In',
  reference: 'Confirm Check In',
}

const STEP_INDEX: Partial<Record<Step, number>> = { reference: 1, result: 2 }

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
  const [bookingId, setBookingId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [booking, setBooking] = useState<CheckinBooking | null>(null)

  const lookup = useLookupBooking()

  const goEnter = () => {
    setError(null)
    setStep('reference')
  }

  const find = async () => {
    setError(null)
    try {
      setBooking(await lookup.mutateAsync(bookingId))
      setStep('result')
    } catch (err) {
      // Stays on this step with the field intact. A wrong code is usually one wrong
      // character, and clearing the box would make them key the whole thing again.
      setError(lookupErrorMessage(err))
    }
  }

  const restart = () => {
    setStep('method')
    setBookingId('')
    setError(null)
    setBooking(null)
  }

  const backHandlers: Record<Step, () => void> = {
    method: onHome,
    reference: () => setStep('method'),
    result: restart,
  }

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <TopBar centerTitle={TITLES[step]} onLogoClick={onHome} />

      <main className="flex min-h-0 flex-1 flex-col items-center justify-center-safe gap-8 overflow-y-auto px-4 py-[clamp(1.5rem,4vh,3rem)]">
        {step === 'method' && <ChooseMethod onHaveBooking={goEnter} onBookNow={onBookNow} />}

        {step === 'reference' && (
          <EnterBookingId
            bookingId={bookingId}
            setBookingId={setBookingId}
            error={error}
            searching={lookup.isPending}
            onSubmit={() => void find()}
          />
        )}

        {step === 'result' && (
          <CheckInResult
            status={booking ? 'found' : 'not-found'}
            booking={booking ?? undefined}
            onRentEquipment={onStore}
            onHome={onHome}
            onRetry={() => {
              setBookingId('')
              goEnter()
            }}
            onBookNow={onBookNow}
          />
        )}
      </main>

      <CheckinFooter
        onBack={backHandlers[step]}
        onHome={step === 'result' ? undefined : onHome}
        step={STEP_INDEX[step]}
        totalSteps={STEP_INDEX[step] ? 2 : undefined}
      />
    </div>
  )
}
