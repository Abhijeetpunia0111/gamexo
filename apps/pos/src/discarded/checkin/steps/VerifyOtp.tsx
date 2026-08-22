import OtpEntry from '../../ui/OtpEntry'
import { maskPhone } from '../useCheckIn'
import type { Country } from '../countries'

export default function VerifyOtp({
  phone,
  country,
  otp,
  setOtp,
  demoCode,
  error,
  verifying,
  resendCooldown,
  onVerify,
  onResend,
}: {
  phone: string
  country: Country
  otp: string
  setOtp: (v: string) => void
  demoCode: string
  error: string | null
  verifying: boolean
  resendCooldown: number
  onVerify: () => void
  onResend: () => void
}) {
  return (
    <OtpEntry
      helperText={`Verify the OTP sent to +${country.dial} ${maskPhone(phone)}`}
      otp={otp}
      setOtp={setOtp}
      demoCode={demoCode}
      error={error}
      verifying={verifying}
      verifyingLabel="Verifying…"
      verifyLabel="Verify Number"
      resendCooldown={resendCooldown}
      onVerify={onVerify}
      onResend={onResend}
    />
  )
}
