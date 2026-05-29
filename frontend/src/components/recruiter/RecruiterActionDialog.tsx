import type { RecruiterActionItem } from '@/api/types'

export function isDestructiveAction(a: RecruiterActionItem): boolean {
  return a.event_type.toLowerCase().includes('reject')
}

type RecruiterActionDialogProps = {
  action: RecruiterActionItem
  reason: string
  actorId: string
  formError: string | null
  isPending: boolean
  onReasonChange: (v: string) => void
  onActorIdChange: (v: string) => void
  onCancel: () => void
  onConfirm: () => void
}

export function RecruiterActionDialog({
  action,
  reason,
  actorId,
  formError,
  isPending,
  onReasonChange,
  onActorIdChange,
  onCancel,
  onConfirm,
}: RecruiterActionDialogProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="presentation"
      onClick={() => !isPending && onCancel()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="action-dialog-title"
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="action-dialog-title" className="text-lg font-semibold text-slate-900">
          {action.label}
        </h2>
        <p className="mt-1 font-mono text-xs text-slate-500">{action.event_type}</p>

        <div className="mt-4 space-y-3">
          <label className="block text-sm font-medium text-slate-700">
            Reason (required)
            <textarea
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm"
              rows={3}
              value={reason}
              onChange={(e) => onReasonChange(e.target.value)}
              placeholder="Human justification for audit trail"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Actor id
            <input
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm"
              value={actorId}
              onChange={(e) => onActorIdChange(e.target.value)}
            />
          </label>
        </div>

        {formError && (
          <p className="mt-3 text-sm text-red-700" role="alert">
            {formError}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50 disabled:opacity-50"
            disabled={isPending}
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className={
              isDestructiveAction(action)
                ? 'rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:opacity-50'
                : 'rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50'
            }
            disabled={isPending}
            onClick={onConfirm}
          >
            {isPending ? 'Submitting…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}
