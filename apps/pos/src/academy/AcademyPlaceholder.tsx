import { GraduationCap } from 'lucide-react'
import { TopBar } from '../ui/TopBar'
import { CheckinFooter } from '../checkin/Chrome'

/** The academy module (attendance + membership) isn't built yet — this keeps the tile
 *  on Home from dead-ending while that flow gets designed next. */
export default function AcademyPlaceholder({ onHome }: { onHome: () => void }) {
  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <TopBar centerTitle="Academy" onLogoClick={onHome} />

      <main className="flex min-h-0 flex-1 flex-col items-center justify-center-safe gap-4 overflow-y-auto px-4 py-10 text-center">
        <span className="flex size-16 items-center justify-center rounded-full bg-surface-muted text-muted">
          <GraduationCap size={30} strokeWidth={1.75} />
        </span>
        <div className="flex flex-col gap-1.5">
          <p className="font-display text-2xl font-bold text-ink">Coming soon</p>
          <p className="max-w-xs text-sm text-muted">
            Student attendance and membership management are on the way.
          </p>
        </div>
      </main>

      <CheckinFooter onHome={onHome} />
    </div>
  )
}
