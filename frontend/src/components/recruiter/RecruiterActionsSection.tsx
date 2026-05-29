import type { RecruiterActionItem } from '@/api/types'
import { isDestructiveAction } from '@/components/recruiter/RecruiterActionDialog'
import { actionsByGroup } from '@/lib/actions'
import { formatFieldLabel } from '@/lib/format'

export function RecruiterActionsSection({
  actions,
  onAction,
  compact = false,
}: {
  actions: RecruiterActionItem[]
  onAction: (a: RecruiterActionItem) => void
  compact?: boolean
}) {
  const grouped = actionsByGroup(actions ?? [])
  if (grouped.length === 0) {
    return <span className="text-sm text-slate-400">—</span>
  }
  if (compact) {
    return (
      <div className="flex flex-wrap gap-1">
        {actions.map((a) => {
          const destructive = isDestructiveAction(a)
          return (
            <button
              key={a.event_type}
              type="button"
              title={a.label}
              className={
                destructive
                  ? 'rounded-md border border-red-200 bg-white px-2 py-1 text-xs font-medium text-red-800 hover:bg-red-50'
                  : 'rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-50'
              }
              onClick={() => onAction(a)}
            >
              {a.label}
            </button>
          )
        })}
      </div>
    )
  }
  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Recruiter Actions</h2>
      {grouped.map(({ group, actions: groupActions }) => (
        <div key={group} className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {formatFieldLabel(group)}
          </h3>
          <div className="flex flex-wrap gap-2">
            {groupActions.map((a) => {
              const destructive = isDestructiveAction(a)
              return (
                <button
                  key={a.event_type}
                  type="button"
                  className={
                    destructive
                      ? 'rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-medium text-red-800 shadow-sm hover:bg-red-50'
                      : 'rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50'
                  }
                  onClick={() => onAction(a)}
                >
                  {a.label}
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </section>
  )
}
