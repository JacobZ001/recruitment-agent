import type { ScoringContextResponse } from '@/api/types'
import { NULL_DISPLAY, formatFieldLabel } from '@/lib/format'

type ScoringContextPanelProps = {
  sc: ScoringContextResponse | Record<string, unknown> | null | undefined
  title?: string
}

function renderValue(value: unknown): string {
  if (value == null || value === '') return NULL_DISPLAY
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
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
  const ctx = sc as ScoringContextResponse
  const scalarFields: { key: keyof ScoringContextResponse; value: unknown }[] = [
    { key: 'context_version', value: ctx.context_version },
    { key: 'status', value: ctx.status },
    { key: 'organization_authoring_text', value: ctx.organization_authoring_text },
    { key: 'recruiter_actor_authoring_text', value: ctx.recruiter_actor_authoring_text },
    { key: 'job_authoring_text', value: ctx.job_authoring_text },
    { key: 'derived_l2_criteria', value: ctx.derived_l2_criteria },
    { key: 'derived_l3_criteria', value: ctx.derived_l3_criteria },
    { key: 'source_refs', value: ctx.source_refs },
    { key: 'created_at', value: ctx.created_at },
    { key: 'updated_at', value: ctx.updated_at },
    { key: 'ready_at', value: ctx.ready_at },
    { key: 'last_ready_materialized_fingerprint', value: ctx.last_ready_materialized_fingerprint },
    { key: 'materialization_blockers', value: ctx.materialization_blockers },
  ]
  const objectFields: { key: string; value: unknown }[] = [
    { key: 'organization_context', value: ctx.organization_context },
    { key: 'recruiter_actor_context', value: ctx.recruiter_actor_context },
    { key: 'job_context', value: ctx.job_context },
  ]
  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <dl className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {scalarFields.map(({ key, value }) => (
          <div key={String(key)} className="border-b border-slate-100 pb-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {formatFieldLabel(String(key))}
            </dt>
            <dd className="mt-1 whitespace-pre-wrap font-mono text-xs text-slate-900">
              {renderValue(value)}
            </dd>
          </div>
        ))}
        {objectFields.map(({ key, value }) => (
          <div key={key} className="border-b border-slate-100 pb-3 lg:col-span-2">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {formatFieldLabel(key)}
            </dt>
            <dd className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 font-mono text-xs text-slate-900">
              {renderValue(value)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
