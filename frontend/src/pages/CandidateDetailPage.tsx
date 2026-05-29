import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getCandidate } from '@/api/client'
import type { ScoringContextSummary } from '@/api/types'
import { ProfilePane } from '@/components/recruiter/ProfilePane'
import { RecruiterActionDialog } from '@/components/recruiter/RecruiterActionDialog'
import { RecruiterActionsSection } from '@/components/recruiter/RecruiterActionsSection'
import { ScoresPane } from '@/components/recruiter/ScoresPane'
import {
  StageStatusField,
  StageTag,
  StatusTag,
} from '@/components/recruiter/StageStatusTags'
import { ScoreProgressBar } from '@/components/recruiter/ScoreProgressBar'
import { useRecruiterActions } from '@/hooks/useRecruiterActions'
import { NULL_DISPLAY, formatScorePercent } from '@/lib/format'

function HeaderBar({
  candidateId,
  fullName,
  stage,
  statusKind,
  jobTitle,
  organization,
  recruiterIdentity,
  overallValue,
  overallType,
}: {
  candidateId: string
  fullName: string
  stage: string
  statusKind: string
  jobTitle: string | null
  organization: string | null
  recruiterIdentity: string | null
  overallValue: number | null | undefined
  overallType: string | null | undefined
}) {
  return (
    <header className="space-y-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Candidate Details</h1>
        <p className="mt-3 text-4xl font-bold tracking-tight text-slate-950">
          {fullName.trim() || 'Unnamed candidate'}
        </p>
        <p className="mt-2 text-sm text-slate-600">
          <span className="font-medium text-slate-700">Candidate ID:</span>{' '}
          <span className="font-mono">{candidateId}</span>
        </p>
      </div>

      <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Job Title</dt>
          <dd className="mt-1 text-base font-medium text-slate-900">
            {jobTitle?.trim() ? jobTitle : NULL_DISPLAY}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Organization
          </dt>
          <dd className="mt-1 text-base font-medium text-slate-900">
            {organization?.trim() ? organization : NULL_DISPLAY}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Recruiter Identity
          </dt>
          <dd className="mt-1 font-mono text-sm text-slate-900">
            {recruiterIdentity?.trim() ? recruiterIdentity : NULL_DISPLAY}
          </dd>
        </div>
      </dl>

      <div className="flex flex-wrap items-end gap-6 border-t border-slate-100 pt-5">
        <StageStatusField label="Stage">
          <StageTag stage={stage} />
        </StageStatusField>
        <StageStatusField label="Status">
          <StatusTag kind={statusKind} />
        </StageStatusField>
        <div className="min-w-[12rem] flex-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Overall Score
          </span>
          <div className="mt-1.5 flex flex-wrap items-center gap-3">
            <span className="text-3xl font-bold text-indigo-900">
              {formatScorePercent(overallValue ?? null)}
            </span>
            {overallType ? (
              <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-900">
                {overallType}
              </span>
            ) : null}
            <ScoreProgressBar value={overallValue ?? null} />
          </div>
        </div>
      </div>
    </header>
  )
}

export function CandidateDetailPage() {
  const { candidateId = '' } = useParams()
  const actions = useRecruiterActions(candidateId)

  const q = useQuery({
    queryKey: ['candidate', candidateId],
    queryFn: () => getCandidate(candidateId),
    enabled: Boolean(candidateId),
  })

  const sc = q.data?.scoring_context as ScoringContextSummary | undefined
  const fullName =
    q.data?.profile?.full_name?.trim() ||
    q.data?.profile?.headline?.trim() ||
    ''

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm font-medium text-indigo-700 hover:underline">
        ← Back to list
      </Link>

      {q.isPending && (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-600" role="status">
          Loading…
        </div>
      )}

      {q.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
          {q.error instanceof Error ? q.error.message : 'Failed to load candidate'}
        </div>
      )}

      {q.data && (
        <>
          <HeaderBar
            candidateId={candidateId}
            fullName={fullName}
            stage={q.data.stage}
            statusKind={q.data.status.kind}
            jobTitle={sc?.job_title ?? null}
            organization={sc?.organization ?? null}
            recruiterIdentity={sc?.recruiter_actor_id ?? null}
            overallValue={q.data.scores.overall_score?.value}
            overallType={q.data.scores.overall_score?.type ?? null}
          />
          <ProfilePane profile={q.data.profile} />
          <ScoresPane scores={q.data.scores} evaluation={q.data.evaluation} />
          <RecruiterActionsSection
            actions={q.data.available_actions ?? []}
            onAction={actions.openAction}
          />
        </>
      )}

      {actions.dialog.open && (
        <RecruiterActionDialog
          action={actions.dialog.action}
          reason={actions.reason}
          actorId={actions.actorId}
          formError={actions.formError}
          isPending={actions.mutation.isPending}
          onReasonChange={actions.setReason}
          onActorIdChange={actions.setActorId}
          onCancel={() => actions.setDialog({ open: false })}
          onConfirm={() => void actions.submitAction()}
        />
      )}
    </div>
  )
}
