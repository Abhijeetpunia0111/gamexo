import { useEffect, useState } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import Dashboard from './components/Dashboard'
import BookingsPage from './components/BookingsPage'
import BookingFlow from './booking/BookingFlow'
import AddOns from './addons/AddOns'
import ActiveGames from './pos/ActiveGames'
import CourtsOverview from './facility/CourtsOverview'
import NotificationSettings from './manage/NotificationSettings'
import PaymentModes from './manage/PaymentModes'
import StaffManagement from './manage/StaffManagement'
import Coaches from './manage/Coaches'
import Users from './manage/Users'
import Membership from './manage/Membership'
import Invoices from './manage/Invoices'
import Coupons from './manage/Coupons'
import Members from './members/Members'
import Academy from './academy/Academy'
import Equipment from './equipment/Equipment'
import { demoBookings } from './data/booking'
import * as db from './lib/db'
import { useAuth } from './auth/AuthProvider'
import LoginPage from './auth/LoginPage'
import dashboardSquareHeader from './assets/figma/dashboard-square-header.svg'
import bolt from './assets/figma/bolt.svg'
import calendar05 from './assets/figma/calendar-05.svg'
import shoppingCartAdd from './assets/figma/shopping-cart-add.svg'
import dices from './assets/figma/dices.svg'
import storeManagement from './assets/figma/store-management.svg'
import userPlus from './assets/figma/user-plus.svg'
import mortarboard from './assets/figma/mortarboard.svg'
import packageDelivered from './assets/figma/package-delivered.svg'
import helpSquareRounded from './assets/figma/help-square-rounded.svg'
import settings from './assets/figma/settings.svg'
import olympicTorch from './assets/figma/olympic-torch.svg'

export type View =
  | 'dashboard'
  | 'booking'
  | 'addons'
  | 'activeCourts'
  | 'bookings'
  | 'members'
  | 'academy'
  | 'equipment'
  | 'events'
  | 'sales'
  | 'settings'
  | 'helpCenter'
  | 'manageCourts'
  | 'manageCoaches'
  | 'manageUsers'
  | 'manageMembership'
  | 'manageInvoices'
  | 'manageCoupons'
  | 'managePaymentModes'
  | 'manageNotifications'
  | 'manageStaff'

function App() {
  const { status } = useAuth()

  if (status === 'checking') {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-page text-sm text-slate">
        Loading…
      </div>
    )
  }
  if (status === 'anonymous') return <LoginPage />

  return <Shell />
}

function Shell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [view, setView] = useState<View>('dashboard')
  const [prefillCourtId, setPrefillCourtId] = useState<string | null>(null)

  // Screens still on localStorage need their demo rows. Migrated screens read
  // the API instead and ignore this entirely.
  useEffect(() => db.seedBookingsIfEmpty(demoBookings), [])

  const navigate = (next: View) => {
    setView(next)
    setSidebarOpen(false)
  }

  const startBookingForCourt = (courtId: string) => {
    setPrefillCourtId(courtId)
    navigate('booking')
  }

  return (
    <div className="flex h-screen w-full items-stretch overflow-hidden bg-page">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} view={view} onNavigate={navigate} />

      <div className="flex h-screen flex-1 flex-col overflow-hidden border-l border-[#ebf0f4]">
        {view === 'dashboard' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Dashboard" icon={dashboardSquareHeader} />
            <Dashboard />
          </>
        )}
        {view === 'booking' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="New Booking" icon={bolt} dateIcon={calendar05} />
            <BookingFlow
              initialCourtId={prefillCourtId ?? undefined}
              onDone={() => {
                setPrefillCourtId(null)
                navigate('dashboard')
              }}
            />
          </>
        )}
        {view === 'addons' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Add-ons" icon={shoppingCartAdd} dateIcon={calendar05} />
            <AddOns />
          </>
        )}
        {view === 'bookings' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Bookings" icon={calendar05} dateIcon={calendar05} />
            <BookingsPage />
          </>
        )}
        {view === 'activeCourts' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Active Courts" icon={dices} dateIcon={calendar05} />
            <ActiveGames onStartBooking={startBookingForCourt} />
          </>
        )}
        {view === 'members' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Members" icon={userPlus} dateIcon={calendar05} />
            <Members />
          </>
        )}
        {view === 'academy' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Academy" icon={mortarboard} dateIcon={calendar05} />
            <Academy />
          </>
        )}
        {view === 'equipment' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Inventory" icon={packageDelivered} dateIcon={calendar05} />
            <Equipment />
          </>
        )}
        {view === 'manageCourts' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Courts Overview" icon={storeManagement} dateIcon={calendar05} />
            <CourtsOverview onStartBooking={() => navigate('booking')} />
          </>
        )}
        {view === 'manageCoaches' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Coaches" icon={storeManagement} dateIcon={calendar05} />
            <Coaches />
          </>
        )}
        {view === 'manageUsers' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Users" icon={storeManagement} dateIcon={calendar05} />
            <Users />
          </>
        )}
        {view === 'manageMembership' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Membership" icon={storeManagement} dateIcon={calendar05} />
            <Membership />
          </>
        )}
        {view === 'manageInvoices' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Invoices" icon={storeManagement} dateIcon={calendar05} />
            <Invoices />
          </>
        )}
        {view === 'manageCoupons' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Discount Coupons" icon={storeManagement} dateIcon={calendar05} />
            <Coupons />
          </>
        )}
        {view === 'managePaymentModes' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Payment Modes" icon={storeManagement} dateIcon={calendar05} />
            <PaymentModes />
          </>
        )}
        {view === 'manageNotifications' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Notification Settings" icon={storeManagement} dateIcon={calendar05} />
            <NotificationSettings />
          </>
        )}
        {view === 'sales' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Sales" icon={shoppingCartAdd} dateIcon={calendar05} />
            <ComingSoon label="Sales" />
          </>
        )}
        {view === 'events' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Events" icon={olympicTorch} dateIcon={calendar05} />
            <ComingSoon label="Events" />
          </>
        )}
        {view === 'settings' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Settings" icon={settings} dateIcon={calendar05} />
            <ComingSoon label="Settings" />
          </>
        )}
        {view === 'helpCenter' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Help Center" icon={helpSquareRounded} dateIcon={calendar05} />
            <ComingSoon label="Help Center" />
          </>
        )}
        {view === 'manageStaff' && (
          <>
            <Header onMenuClick={() => setSidebarOpen(true)} title="Manage Staff" icon={storeManagement} dateIcon={calendar05} />
            <StaffManagement />
          </>
        )}
      </div>
    </div>
  )
}

function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="rounded-3xl border border-dashed border-border-card bg-white/80 px-10 py-12 text-center shadow-sm">
        <p className="text-xl font-semibold text-ink">{label} is coming soon</p>
        <p className="mt-3 text-sm text-slate">We’re building this experience now. Check back soon for the launch.</p>
      </div>
    </div>
  )
}

export default App
