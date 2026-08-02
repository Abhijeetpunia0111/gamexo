import { useEffect, useState } from 'react'
import { currentUser } from '../data/mockData'
import type { View } from '../App'

import brandLogo from '../assets/figma/brand-logo.svg'
import bolt from '../assets/figma/bolt.svg'
import dashboardSquare from '../assets/figma/dashboard-square.svg'
import dices from '../assets/figma/dices.svg'
import shoppingCartAdd from '../assets/figma/shopping-cart-add.svg'
import calendar from '../assets/figma/calendar.svg'
import storeManagement from '../assets/figma/store-management.svg'
import chevronRight from '../assets/figma/chevron-right.svg'
import packageDelivered from '../assets/figma/package-delivered.svg'
import mortarboard from '../assets/figma/mortarboard.svg'
import olympicTorch from '../assets/figma/olympic-torch.svg'
import helpSquareRounded from '../assets/figma/help-square-rounded.svg'
import settings from '../assets/figma/settings.svg'
import selectorChevron from '../assets/figma/selector-chevron.svg'
import userPlus from '../assets/figma/user-plus.svg'

type NavItem = {
  label: string
  icon: string
  view?: View
  submenu?: boolean
}

const primaryItems: NavItem[] = [
  { label: 'Dashboard', icon: dashboardSquare, view: 'dashboard' },
  { label: 'Active Courts', icon: dices, view: 'activeCourts' },
  { label: 'Add ons', icon: shoppingCartAdd, view: 'addons' },
  { label: 'Bookings', icon: calendar, view: 'bookings' },
  { label: 'Members', icon: userPlus, view: 'members' },
  { label: 'Manage', icon: storeManagement, submenu: true },
  { label: 'Sales', icon: storeManagement, view: 'sales' },
  { label: 'Inventory', icon: packageDelivered, view: 'equipment' },
  { label: 'Academy', icon: mortarboard, view: 'academy' },
  { label: 'Events', icon: olympicTorch, view: 'events' },
]

const manageItems: { label: string; view: View }[] = [
  { label: 'Sports & Courts', view: 'manageCourts' },
  { label: 'Coaches', view: 'manageCoaches' },
  { label: 'Users', view: 'manageUsers' },
  { label: 'Membership', view: 'manageMembership' },
  { label: 'Invoices', view: 'manageInvoices' },
  { label: 'Discount Coupons', view: 'manageCoupons' },
  { label: 'Payment Modes', view: 'managePaymentModes' },
  { label: 'Notifications', view: 'manageNotifications' },
  { label: 'Manage Staff', view: 'manageStaff' },
]

const isManageView = (view: View) => view.startsWith('manage')

export default function Sidebar({
  open,
  onClose,
  view,
  onNavigate,
}: {
  open: boolean
  onClose: () => void
  view: View
  onNavigate: (view: View) => void
}) {
  const [manageOpen, setManageOpen] = useState(isManageView(view))

  useEffect(() => {
    if (isManageView(view)) setManageOpen(true)
  }, [view])

  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex h-screen w-[260px] shrink-0 flex-col gap-8 overflow-y-auto border-r-[1.5px] border-border-soft bg-page p-5 transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex w-full shrink-0 items-center gap-2">
          <img src={brandLogo} alt="" className="size-5" />
          <p className="flex-1 font-display text-[18px] font-semibold text-ink">
            XCourt
          </p>
        </div>

        <nav className="flex w-full flex-1 flex-col justify-between">
          {manageOpen ? (
            <div className="flex w-full flex-col gap-1">
              <button
                type="button"
                onClick={() => setManageOpen(false)}
                className="mb-1 flex h-[38px] w-full items-center gap-2.5 rounded-lg pl-2.5 pr-3 py-2 text-left text-sm font-medium text-ink hover:bg-white/60"
              >
                <img src={chevronRight} alt="" className="size-4 rotate-180" />
                <span>Manage</span>
              </button>

              {manageItems.map((item) => {
                const isActive = item.view === view
                return (
                  <button
                    key={item.view}
                    type="button"
                    onClick={() => onNavigate(item.view)}
                    className={`flex h-[38px] w-full items-center gap-2.5 rounded-lg pl-8 pr-3 py-2 text-left text-sm transition-colors ${
                      isActive
                        ? 'bg-white text-ink shadow-[0px_4px_10px_0px_rgba(0,0,0,0.05),0px_10px_120px_0px_rgba(15,73,106,0.1)]'
                        : 'text-slate hover:bg-white/60'
                    }`}
                  >
                    <span className="flex-1">{item.label}</span>
                  </button>
                )
              })}
            </div>
          ) : (
            <div className="flex w-full flex-col gap-1">
              <button
                type="button"
                onClick={() => onNavigate('booking')}
                className="flex h-[38px] w-full items-center gap-2.5 rounded-lg bg-lime pl-2.5 pr-3 py-2 shadow-[0px_4px_10px_0px_rgba(0,0,0,0.05),0px_10px_120px_0px_rgba(15,73,106,0.1)]"
              >
                <img src={bolt} alt="" className="size-[18px]" />
                <span className="flex-1 text-left text-sm text-lime-ink">
                  New Booking
                </span>
              </button>

              {primaryItems.map((item) => {
                const isActive = item.view ? item.view === view : item.label === 'Manage' && isManageView(view)
                return (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => {
                      if (item.label === 'Manage') {
                        setManageOpen(true)
                        onNavigate('manageCourts')
                        return
                      }
                      if (item.view) onNavigate(item.view)
                    }}
                    className={`flex h-[38px] w-full items-center gap-2.5 rounded-lg pl-2.5 pr-3 py-2 text-left text-sm text-slate transition-colors ${
                      isActive
                        ? 'bg-white shadow-[0px_4px_10px_0px_rgba(0,0,0,0.05),0px_10px_120px_0px_rgba(15,73,106,0.1)]'
                        : 'hover:bg-white/60'
                    }`}
                  >
                    <img src={item.icon} alt="" className="size-[18px]" />
                    <span className="flex-1">{item.label}</span>
                    {item.submenu && <img src={chevronRight} alt="" className="size-4" />}
                  </button>
                )
              })}
            </div>
          )}

          <div className="flex w-full shrink-0 flex-col gap-3">
            <div className="flex w-full flex-col gap-1">
              <button
                type="button"
                onClick={() => onNavigate('helpCenter')}
                className="flex h-[38px] w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-slate hover:bg-white/60"
              >
                <img src={helpSquareRounded} alt="" className="size-[18px]" />
                <span>Help Center</span>
              </button>
              <button
                type="button"
                onClick={() => onNavigate('settings')}
                className="flex h-[38px] w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-slate hover:bg-white/60"
              >
                <img src={settings} alt="" className="h-[18px] w-auto" />
                <span>Settings</span>
              </button>
            </div>

            <div className="h-px w-full bg-border-soft" />

            <button
              type="button"
              className="flex w-full items-center gap-3 rounded-lg p-3 text-left hover:bg-white/60"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-lime-ink text-[12px] font-semibold text-lime">
                {currentUser.initials}
              </div>
              <div className="flex flex-1 flex-col justify-center gap-1">
                <p className="text-sm font-semibold tracking-[-0.14px] text-ink">
                  {currentUser.name}
                </p>
                <p className="text-[11px] font-medium text-slate">{currentUser.role}</p>
              </div>
              <img src={selectorChevron} alt="" className="h-3 w-auto shrink-0" />
            </button>
          </div>
        </nav>
      </aside>
    </>
  )
}
