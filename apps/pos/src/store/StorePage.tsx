import { useState } from 'react'
import { ImageOff, ShoppingCart } from 'lucide-react'
import { useEquipment, type EquipmentItem } from '../api/hooks'
import { money } from '../lib/format'
import { TopBar } from '../ui/TopBar'
import { CheckinFooter } from '../checkin/Chrome'
import CheckoutSheet from './CheckoutSheet'
import addIcon from '../assets/figma/shop/add.svg'
import removeIcon from '../assets/figma/shop/remove.svg'

function ProductCard({
  item,
  qty,
  onAdd,
  onQty,
}: {
  item: EquipmentItem
  qty: number
  onAdd: () => void
  onQty: (qty: number) => void
}) {
  const soldOut = item.stock <= 0
  const active = qty > 0
  const atLimit = qty >= item.stock

  return (
    <div
      role="button"
      tabIndex={soldOut ? -1 : 0}
      aria-disabled={soldOut}
      onClick={() => !active && !soldOut && onAdd()}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !active && !soldOut) {
          e.preventDefault()
          onAdd()
        }
      }}
      className={`flex aspect-square w-full flex-col items-stretch gap-[clamp(0.75rem,1.5vw,1rem)] border-4 bg-surface p-[clamp(0.75rem,1.4vw,1rem)] text-left transition-colors ${
        active ? 'border-lime' : 'border-transparent'
      } ${soldOut ? 'cursor-not-allowed opacity-50' : !active ? 'cursor-pointer' : ''}`}
    >
      <div className="relative w-full flex-1 overflow-hidden">
        {item.imageUrl ? (
          <img src={item.imageUrl} alt="" className="size-full object-contain" />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-1.5 bg-surface-muted text-muted">
            <ImageOff size={22} strokeWidth={1.5} />
            <span className="text-xs font-medium">No image</span>
          </div>
        )}

        {active && (
          <div
            onClick={(e) => e.stopPropagation()}
            className="absolute bottom-2 right-2 flex items-center gap-1.5 rounded-lg bg-[#202020] px-2 py-1.5 shadow-[0px_8px_11px_-6px_rgba(0,0,0,0.12)]"
          >
            <button
              type="button"
              aria-label={`Remove one ${item.name}`}
              onClick={() => onQty(qty - 1)}
              className="flex size-4 items-center justify-center text-white"
            >
              <img src={removeIcon} alt="" className="size-full" />
            </button>
            <span className="w-3 text-center text-[11px] font-semibold text-white">{qty}</span>
            <button
              type="button"
              aria-label={`Add one more ${item.name}`}
              disabled={atLimit}
              onClick={() => onQty(qty + 1)}
              className="flex size-4 items-center justify-center text-white disabled:opacity-40"
            >
              <img src={addIcon} alt="" className="size-full" />
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-col items-start gap-0.5">
        <p className="text-[clamp(0.9375rem,1.3vw,1.125rem)] font-bold text-ink">{item.name}</p>
        <p className="text-[clamp(0.8125rem,1vw,0.875rem)] font-medium text-muted">
          {soldOut ? 'Sold out' : money(item.price)}
        </p>
      </div>
    </div>
  )
}

export default function StorePage({ onHome }: { onHome: () => void }) {
  const equipmentQuery = useEquipment()
  const items = equipmentQuery.data ?? []
  const categories = ['All', ...new Set(items.map((i) => i.category).filter(Boolean))]
  const [category, setCategory] = useState('All')
  const [tray, setTray] = useState<Record<string, number>>({})
  const [checkoutOpen, setCheckoutOpen] = useState(false)

  const shown = category === 'All' ? items : items.filter((i) => i.category === category)
  const gridColumns = Math.max(1, Math.ceil(shown.length / 2))

  const setQty = (id: string, qty: number, max: number) => {
    setTray((t) => {
      const next = { ...t }
      if (qty > 0) next[id] = Math.min(qty, max)
      else delete next[id]
      return next
    })
  }

  const trayCount = Object.values(tray).reduce((a, qty) => a + qty, 0)
  const clearTray = () => setTray({})

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto">
      <TopBar centerTitle="Shop" onLogoClick={onHome} />

      <main className="flex flex-1 flex-col gap-[clamp(1.25rem,2.5vw,1.625rem)] px-[clamp(1.25rem,3vw,3rem)] py-[clamp(1rem,2vw,1.5rem)]">
        {equipmentQuery.isPending ? (
          <p className="text-sm text-muted">Loading inventory…</p>
        ) : equipmentQuery.error ? (
          <p role="alert" className="text-sm text-negative">
            Could not load equipment: {equipmentQuery.error instanceof Error ? equipmentQuery.error.message : 'unknown error'}
          </p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted">No equipment configured for sale yet.</p>
        ) : (
          <>
            <div className="flex w-full flex-wrap gap-3">
              {categories.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCategory(c)}
                  className={`flex h-[clamp(2.75rem,4.5vw,3.25rem)] min-w-[85px] items-center justify-center rounded-xl px-[clamp(1rem,1.6vw,1.125rem)] text-[clamp(0.9375rem,1vw,1rem)] font-semibold transition-colors ${
                    category === c ? 'bg-ink text-white' : 'bg-surface text-ink hover:bg-surface-muted'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>

            <div
              className="grid grid-flow-col grid-rows-2 gap-[clamp(0.75rem,1.6vw,1rem)] overflow-x-auto pb-2"
              style={{ gridTemplateColumns: `repeat(${gridColumns}, minmax(16rem, 1fr))` }}
            >
              {shown.map((item) => (
                <ProductCard
                  key={item.id}
                  item={item}
                  qty={tray[item.id] || 0}
                  onAdd={() => setQty(item.id, 1, item.stock)}
                  onQty={(qty) => setQty(item.id, qty, item.stock)}
                />
              ))}
            </div>
          </>
        )}
      </main>

      <CheckinFooter
        onBack={onHome}
        onHome={onHome}
        rightExtra={
          <button
            type="button"
            disabled={trayCount === 0}
            onClick={() => setCheckoutOpen(true)}
            className="flex items-center gap-2.5 rounded-xl bg-ink py-1.5 pl-1.5 pr-4 text-[clamp(0.9375rem,1vw,1rem)] font-semibold text-white transition-opacity disabled:opacity-40"
          >
            <span className="flex items-center gap-1.5 rounded-lg bg-lime px-2 py-1.5 text-ink">
              <ShoppingCart size={18} strokeWidth={2} />
              {trayCount}
            </span>
            Continue
          </button>
        }
      />

      {checkoutOpen && (
        <CheckoutSheet
          tray={tray}
          items={items}
          onClose={() => setCheckoutOpen(false)}
          onDone={() => {
            clearTray()
            setCheckoutOpen(false)
          }}
        />
      )}
    </div>
  )
}
