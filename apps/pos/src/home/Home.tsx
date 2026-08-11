import { useState } from 'react'
import { LogOut } from 'lucide-react'
import type { View } from '../App'
import { TopBar } from '../ui/TopBar'
import { useAuth } from '../auth/AuthProvider'
import checkinIllustration from '../assets/figma/home/checkin-illustration.png'
import shopIllustration from '../assets/figma/home/shop-illustration.png'
import academyIllustration from '../assets/figma/home/academy-illustration.png'
import checkoutIcon from '../assets/figma/checkin/checkout.svg'

function Tile({
  image,
  title,
  detail,
  onClick,
}: {
  image: string
  title: string
  detail: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-[296px] shrink-0 flex-col items-center gap-[clamp(1rem,2vw,1.375rem)] rounded-2xl bg-surface px-4 pb-[clamp(1.5rem,3vw,2rem)] pt-3.5 transition-transform hover:-translate-y-1 min-[650px]:w-full min-[650px]:max-w-[296px] min-[650px]:flex-1 min-[650px]:shrink"
    >
      <div className="h-[clamp(11rem,20vw,17.3125rem)] w-full">
        <img src={image} alt="" className="size-full object-contain" />
      </div>
      <div className="flex flex-col items-center gap-3.5 text-center">
        <p className="font-display text-[clamp(1.2rem,2vw,1.375rem)] font-bold text-ink">{title}</p>
        <p className="text-[clamp(0.9375rem,1.3vw,1rem)] font-medium text-muted">{detail}</p>
      </div>
    </button>
  )
}

export default function Home({ onNavigate }: { onNavigate: (view: View) => void }) {
  const { logout } = useAuth()
  const [showSignOut, setShowSignOut] = useState(false)

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <TopBar
        onLogoClick={() => onNavigate('home')}
        onLogoDoubleClick={() => setShowSignOut((v) => !v)}
        logoMenu={
          showSignOut && (
            <button
              type="button"
              onClick={() => {
                setShowSignOut(false)
                logout()
              }}
              className="absolute left-0 top-full z-10 mt-2 flex items-center gap-2 whitespace-nowrap rounded-xl bg-surface px-4 py-3 text-sm font-medium text-muted shadow-[0px_12px_17px_-9px_rgba(0,0,0,0.12)] hover:text-ink"
            >
              <LogOut size={16} strokeWidth={1.75} />
              Sign out
            </button>
          )
        }
        rightExtra={
          <button
            type="button"
            onClick={() => onNavigate('checkout')}
            className="flex h-full items-center gap-2 rounded-xl bg-ink px-[clamp(1rem,1.8vw,1.375rem)] py-3 text-[clamp(0.9375rem,1vw,0.9375rem)] font-bold text-white"
          >
            <img src={checkoutIcon} alt="" className="size-[clamp(1.1rem,1.4vw,1.5rem)]" />
            Checkout
          </button>
        }
      />

      <main className="flex min-h-0 flex-1 flex-col items-center justify-center-safe gap-[clamp(1.75rem,4vh,3.125rem)] overflow-y-auto px-10 py-10">
        <div className="flex flex-col items-center gap-1 text-center">
          <p className="font-display text-[clamp(1.5rem,3vw,2.25rem)] font-bold text-ink">Welcome to Xcourt</p>
          <p className="text-[clamp(0.9375rem,1.2vw,1rem)] font-medium text-muted">
            What would you like to do today?
          </p>
        </div>

        <div className="flex w-full max-w-[960px] flex-row items-stretch justify-start gap-5 overflow-x-auto px-1 pb-2 min-[650px]:justify-center min-[650px]:overflow-visible min-[650px]:px-0 min-[650px]:pb-0">
          <Tile
            image={checkinIllustration}
            title="Check In"
            detail="Already have a Booking or Book now"
            onClick={() => onNavigate('checkin')}
          />
          <Tile
            image={shopIllustration}
            title="Shop"
            detail="Rent any equipment, shoes, and more ."
            onClick={() => onNavigate('store')}
          />
          <Tile
            image={academyIllustration}
            title="Academy"
            detail="Student attendance & membership"
            onClick={() => onNavigate('academy')}
          />
        </div>
      </main>
    </div>
  )
}
