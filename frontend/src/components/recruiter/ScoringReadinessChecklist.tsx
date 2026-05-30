import type { ScoringContextResponse } from '@/api/types'
import {
  blockerTargetDimension,
  isMaterializedCriteriaBlocker,
  mapMaterializationBlockers,
} from '@/lib/scoringContextBlockers'

export type ChecklistScrollTarget = 'organization' | 'recruiter_actor' | 'job' | 'materialized'

type ScoringReadinessChecklistProps = {
  context: ScoringContextResponse | undefined
  isLoading: boolean
  onOpenDimension: (target: ChecklistScrollTarget) => void
}

type ItemStatus = 'done' | 'pending' | 'warning'

function StatusIcon({ status }: { status: ItemStatus }) {
  if (status === 'done') {
    return (
      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs text-emerald-800">
        ✓
      </span>
    )
  }
  if (status === 'warning') {
    return (
      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs text-amber-900">
        ⚠
      </span>
    )
  }
  return (
    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-300 text-xs text-slate-500">
      ○
    </span>
  )
}

function orgConfirmed(ctx: ScoringContextResponse): boolean {
  return !!ctx.organization_authoring_text?.trim()
}

function prefsConfirmed(ctx: ScoringContextResponse): boolean {
  return !!ctx.recruiter_actor_authoring_text?.trim()
}

function roleConfirmed(ctx: ScoringContextResponse): boolean {
  return !!ctx.job_authoring_text?.trim()
}

export function ScoringReadinessChecklist({
  context,
  isLoading,
  onOpenDimension,
}: ScoringReadinessChecklistProps) {
  const ready = context?.status === 'ready'
  const blockers = context?.materialization_blockers ?? []
  const materializedBlockers = blockers.filter(isMaterializedCriteriaBlocker)
  const proseComplete = context
    ? orgConfirmed(context) && prefsConfirmed(context) && roleConfirmed(context)
    : false

  let criteriaStatus: ItemStatus = 'pending'
  let criteriaDetail: string | null = null

  if (ready) {
    criteriaStatus = 'done'
    criteriaDetail = 'Ready to add candidates.'
  } else if (proseComplete && materializedBlockers.length > 0) {
    criteriaStatus = 'warning'
    criteriaDetail = mapMaterializationBlockers(materializedBlockers).join(' ')
  } else if (proseComplete && blockers.length > 0) {
    criteriaStatus = 'warning'
    criteriaDetail = mapMaterializationBlockers(blockers).join(' ')
  } else if (proseComplete) {
    criteriaStatus = 'pending'
    criteriaDetail = 'All sections confirmed — scoring criteria will materialize on refresh.'
  } else {
    criteriaDetail = 'Confirm all three sections in Scoring context first.'
  }

  const items: {
    key: ChecklistScrollTarget
    label: string
    status: ItemStatus
    detail?: string | null
  }[] = [
    {
      key: 'organization',
      label: 'Organization described & confirmed',
      status: context && orgConfirmed(context) ? 'done' : 'pending',
    },
    {
      key: 'recruiter_actor',
      label: 'Your preferences described & confirmed',
      status: context && prefsConfirmed(context) ? 'done' : 'pending',
    },
    {
      key: 'job',
      label: 'Role described & confirmed',
      status: context && roleConfirmed(context) ? 'done' : 'pending',
    },
    {
      key: 'materialized',
      label: 'Scoring criteria materialized',
      status: criteriaStatus,
      detail: criteriaDetail,
    },
  ]

  const firstMaterializedBlockerTarget = materializedBlockers[0]
    ? blockerTargetDimension(materializedBlockers[0])
    : 'materialized'

  return (
    <section
      className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
      aria-label="Scoring readiness checklist"
    >
      <h2 className="text-base font-semibold text-slate-900">Scoring readiness</h2>
      <p className="mt-1 text-sm text-slate-600">
        Complete these steps before creating candidates. Click an item to open the matching section.
      </p>
      {isLoading && <p className="mt-3 text-sm text-slate-500">Loading scoring context…</p>}
      <ul className="mt-4 space-y-3">
        {items.map((item) => (
          <li key={item.key}>
            <button
              type="button"
              className="flex w-full items-start gap-3 rounded-md px-2 py-1.5 text-left hover:bg-slate-50"
              onClick={() =>
                onOpenDimension(
                  item.key === 'materialized' && !ready && materializedBlockers.length > 0
                    ? firstMaterializedBlockerTarget
                    : item.key,
                )
              }
            >
              <StatusIcon status={item.status} />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-slate-900">{item.label}</span>
                {item.detail ? (
                  <span
                    className={`mt-0.5 block text-xs ${
                      item.status === 'warning' ? 'text-amber-900' : 'text-slate-600'
                    }`}
                  >
                    {item.detail}
                  </span>
                ) : null}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {ready && (
        <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          Ready to add candidates — you can upload a candidate PDF below.
        </p>
      )}
    </section>
  )
}
