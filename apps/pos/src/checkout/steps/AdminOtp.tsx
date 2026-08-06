import OtpEntry from '../../ui/OtpEntry'

/** Staff-side authorization, not the customer's — confirms an admin is standing at the
 *  counter approving the settlement, same boxed-OTP pattern as the check-in phone step. */
export default function AdminOtp({
  otp,
  setOtp,
  demoCode,
  error,
  verifying,
  resendCooldown,
  onVerify,
  onResend,
}: {
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
      helperText="Enter the admin OTP to authorize this settlement"
      demoLabel="Test mode — the admin OTP is"
      otp={otp}
      setOtp={setOtp}
      demoCode={demoCode}
      error={error}
      verifying={verifying}
      verifyingLabel="Settling…"
      verifyLabel="Confirm & Settle"
      resendCooldown={resendCooldown}
      onVerify={onVerify}
      onResend={onResend}
    />
  )
}
