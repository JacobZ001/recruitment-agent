import { useEffect, useRef, type ReactNode } from 'react'

type ModalBaseProps = {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}

export function ModalBase({ open, title, onClose, children }: ModalBaseProps) {
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
    if (open) panelRef.current?.focus()
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-slate-900/50"
        aria-label="Close Modal"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="sc-modal-title"
        tabIndex={-1}
        className="relative w-full max-w-2xl rounded-lg border border-slate-200 bg-white shadow-xl outline-none"
      >
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h3 id="sc-modal-title" className="text-lg font-semibold text-slate-900">
            {title}
          </h3>
          <button
            type="button"
            className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            aria-label="Close"
            onClick={onClose}
          >
            ✕
          </button>
        </header>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  )
}

