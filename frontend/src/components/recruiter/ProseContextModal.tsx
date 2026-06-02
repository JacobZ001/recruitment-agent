import { useEffect, useState } from 'react'
import { ModalBase } from '@/components/recruiter/ModalBase'

type ProseContextModalProps = {
  open: boolean
  title: string
  initialText: string
  isSaving: boolean
  error: string | null
  onCancel: () => void
  onConfirm: (text: string) => void
}

export function ProseContextModal({
  open,
  title,
  initialText,
  isSaving,
  error,
  onCancel,
  onConfirm,
}: ProseContextModalProps) {
  const [text, setText] = useState(initialText)

  useEffect(() => {
    if (open) setText(initialText)
  }, [open, initialText])

  return (
    <ModalBase open={open} title={title} onClose={onCancel}>
      <textarea
        className="min-h-[220px] w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={isSaving}
      />
      {error ? (
        <p className="mt-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
          disabled={isSaving}
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="button"
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          disabled={isSaving}
          onClick={() => onConfirm(text)}
        >
          Confirm
        </button>
      </div>
    </ModalBase>
  )
}

