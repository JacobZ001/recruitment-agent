import type { ScoringContextSummary } from '@/api/types'
import { NULL_DISPLAY, formatFieldLabel } from '@/lib/format'

type ScoringContextPanelProps = {
  sc: ScoringContextSummary | Record<string, unknown> | null | undefined
  title?: string
}

export function ScoringContextPanel({
  sc,
  title = 'Scoring Context',
}: ScoringContextPanelProps) {
  if (!sc) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="mt-2 text-sm text-slate-500">None active for this view.</p>
      </section>
    )
  }
  const row = sc as Record<string, unknown>
  const fields: { key: string; value: unknown }[] = [
    { key: 'context_version', value: row.context_version },
    { key: 'status', value: row.status },
    { key: 'organization', value: row.organization },
    { key: 'job_title', value: row.job_title },
    { key: 'recruiter_actor_id', value: row.recruiter_actor_id },
  ]
  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <p className="text-xs text-slate-500">Read-only active scoring context (list testing surface).</p>
      <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {fields.map(({ key, value }) => (
          <div key={key} className="border-b border-slate-100 pb-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {formatFieldLabel(key)}
            </dt>
            <dd className="mt-1 text-sm text-slate-900">
              {value != null && value !== '' ? String(value) : NULL_DISPLAY}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
