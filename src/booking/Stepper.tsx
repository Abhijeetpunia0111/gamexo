export const STEPS = ['Select Sports & Court', 'Date & Time', 'Player Details', 'Add Ons', 'Payments'] as const

export default function Stepper({
  current,
  onSelect,
}: {
  current: number
  onSelect: (step: number) => void
}) {
  return (
    <div className="flex w-full items-center gap-[50px] overflow-x-auto rounded-xl bg-white p-5">
      {STEPS.map((label, i) => {
        const step = i + 1
        const active = step === current
        const visited = step < current
        return (
          <div
            key={label}
            onClick={() => visited && onSelect(step)}
            className={`flex shrink-0 items-center gap-2.5 ${active ? '' : 'opacity-50'} ${visited ? 'cursor-pointer' : ''}`}
          >
            <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-lime">
              <p className="text-base font-semibold leading-[1.2] text-black">{step}</p>
            </div>
            <p className="whitespace-nowrap text-base font-semibold leading-[1.2] text-black">{label}</p>
          </div>
        )
      })}
    </div>
  )
}
