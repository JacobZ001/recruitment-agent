import { ModalBase } from '@/components/recruiter/ModalBase'

type ConfirmReplaceFormModalProps = {
  open: boolean
  onCancel: () => void
  onConfirm: () => void
}

export function ConfirmReplaceFormModal({ open, onCancel, onConfirm }: ConfirmReplaceFormModalProps) {
  return (
    <ModalBase open={open} title="Replace Form Answers?" onClose={onCancel}>
      <p className="text-sm text-slate-700">This Replaces Your Form Answers.</p>
      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="button"
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          onClick={onConfirm}
        >
          Replace And Continue
        </button>
      </div>
    </ModalBase>
  )
}

