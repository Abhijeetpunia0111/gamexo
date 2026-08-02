import { Menu } from 'lucide-react'

import dashboardSquareHeader from '../assets/figma/dashboard-square-header.svg'
import search from '../assets/figma/search.svg'
import bell from '../assets/figma/bell.svg'
import calendarPlus from '../assets/figma/calendar-plus.svg'
import userPlus from '../assets/figma/user-plus.svg'

const today = new Date().toLocaleDateString('en-US', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

export default function Header({
  onMenuClick,
  title = 'Dashboard',
  icon = dashboardSquareHeader,
  dateIcon = calendarPlus,
}: {
  onMenuClick: () => void
  title?: string
  icon?: string
  dateIcon?: string
}) {
  return (
    <header className="flex h-[72px] w-full shrink-0 items-center gap-2 border-b-[1.5px] border-border-soft px-4 py-4 sm:gap-3 sm:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        aria-label="Open menu"
        className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border-input bg-white lg:hidden"
      >
        <Menu size={18} className="text-ink" />
      </button>

      <div className="flex flex-1 items-center gap-2 min-w-0">
        <img src={icon} alt="" className="hidden size-6 shrink-0 sm:block" />
        <p className="flex-1 truncate text-xl font-medium text-ink">{title}</p>
      </div>

      <button
        type="button"
        className="hidden h-9 items-center gap-2.5 rounded-lg border border-border-input bg-white px-3.5 py-2.5 shadow-[0px_1px_2px_0px_rgba(82,88,102,0.09)] sm:flex sm:max-w-[420px] sm:flex-1"
      >
        <img src={search} alt="" className="size-[18px] shrink-0" />
        <span className="truncate text-left text-sm text-muted">Search Anything...</span>
      </button>

      <button
        type="button"
        aria-label="Search"
        className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border-input bg-white sm:hidden"
      >
        <img src={search} alt="" className="size-[18px]" />
      </button>

      <button
        type="button"
        className="relative flex size-9 shrink-0 items-center justify-center rounded-lg border border-border-input bg-white drop-shadow-[0px_1px_1px_rgba(82,88,102,0.09)]"
      >
        <img src={bell} alt="" className="h-[18px] w-auto" />
        <span className="absolute -top-0.5 right-[7px] size-2 rounded-full border border-white/10 bg-notify shadow-[0px_2px_5px_-1px_rgba(0,0,0,0.12)]" />
      </button>

      <button
        type="button"
        className="hidden h-9 shrink-0 items-center gap-2.5 rounded-lg border border-border-input bg-white px-3.5 py-2.5 md:flex"
      >
        <span className="whitespace-nowrap text-sm text-ink">{today}</span>
        <img src={dateIcon} alt="" className="size-[18px]" />
      </button>

      <button
        type="button"
        className="flex h-9 shrink-0 items-center justify-end gap-2 rounded-lg px-3 shadow-[0px_4px_10px_0px_rgba(0,0,0,0.05),0px_10px_120px_0px_rgba(15,73,106,0.1)] sm:gap-3 sm:px-3.5"
        style={{
          backgroundImage:
            'linear-gradient(106.6deg, rgb(41, 41, 41) 2.09%, rgb(26, 26, 26) 100%)',
        }}
      >
        <img src={userPlus} alt="" className="h-[17px] w-auto" />
        <span className="hidden whitespace-nowrap text-sm font-medium text-white sm:inline">
          New Walk-in
        </span>
      </button>
    </header>
  )
}
