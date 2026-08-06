import type { ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import logoMark from '../assets/figma/logo-mark.svg'
import languageIcon from '../assets/figma/checkin/language.svg'

/** Static for now — there is only one locale wired up. Kept as a real button (not a
 *  disabled-looking one) since the design commits to it being a live control later. */
export function LanguagePill() {
  return (
    <button
      type="button"
      title="Language — more coming soon"
      className="flex h-full items-center gap-2.5 rounded-xl bg-surface px-[clamp(0.75rem,1.4vw,1.125rem)] py-3 text-ink shadow-[0px_12px_17px_-9px_rgba(0,0,0,0.12)]"
    >
      <img src={languageIcon} alt="" className="size-[clamp(1.1rem,1.4vw,1.5rem)]" />
      <span className="whitespace-nowrap text-[clamp(0.875rem,1vw,1rem)] font-medium">English</span>
      <ChevronDown size={12} strokeWidth={2.5} />
    </button>
  )
}

export function TopBar({
  centerTitle,
  rightExtra,
  onLogoClick,
}: {
  centerTitle?: string
  rightExtra?: ReactNode
  onLogoClick: () => void
}) {
  return (
    <header className="relative flex w-full shrink-0 items-center justify-between gap-4 px-[clamp(1.25rem,3vw,3.25rem)] py-[clamp(1.1rem,2.4vw,1.75rem)]">
      <button type="button" onClick={onLogoClick} className="flex shrink-0 items-center gap-2.5">
        <img src={logoMark} alt="" className="h-[clamp(1.75rem,2.3vw,2.2rem)] w-auto" />
        <span className="font-display text-[clamp(1rem,1.05vw,1.1rem)] font-bold text-ink">XCSports</span>
      </button>

      {centerTitle && (
        <p className="absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 whitespace-nowrap text-[clamp(1.1rem,1.6vw,1.375rem)] font-semibold text-ink md:block">
          {centerTitle}
        </p>
      )}

      <div className="flex shrink-0 items-center gap-[clamp(0.625rem,1.2vw,1.25rem)]">
        <LanguagePill />
        {rightExtra}
      </div>
    </header>
  )
}
