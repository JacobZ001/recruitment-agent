import { useEffect, useRef, type ReactNode } from 'react'

type ScoringContextDrawerProps = {
  open: boolean
  onClose: () => void
  title?: string
  showBadge?: boolean
  children: ReactNode
}

export function ScoringContextDrawer({
  open,
  onClose,
  title = 'Scoring context',
  showBadge = false,
  children,
}: ScoringContextDrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  useEffect(() => {
    if (open) {
      panelRef.current?.focus()
    }
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-slate-900/40"
        aria-label="Close scoring context panel"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="scoring-context-drawer-title"
        tabIndex={-1}
        className="relative flex h-full w-full max-w-lg flex-col border-l border-slate-200 bg-white shadow-xl outline-none"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-slate-200 px-5 py-4">
          <div className="flex items-center gap-2">
            <h2 id="scoring-context-drawer-title" className="text-lg font-semibold text-slate-900">
              {title}
            </h2>
            {showBadge ? (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
                Not ready
              </span>
            ) : null}
          </div>
          <button
            type="button"
            className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            aria-label="Close"
            onClick={onClose}
          >
            ✕
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  )
}
