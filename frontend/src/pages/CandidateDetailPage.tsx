import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiRequestError, extractApiError, getCandidate, postCandidateAction } from '@/api/client'
import type { CandidateProfile, CandidateViewResponse, RecruiterActionItem, ScoreCriterion } from '@/api/types'
import { actionsByGroup } from '@/lib/actions'

function isDestructiveAction(a: RecruiterActionItem): boolean {
  return a.event_type.toLowerCase().includes('reject')
}

function ScoreBlock({ scores }: { scores: CandidateViewResponse['scores'] }) {
  const overall = scores.overall_score
  const criteria = (scores.criteria ?? []) as ScoreCriterion[]
  return (
    <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Scores</h2>
      <p className="text-xs text-slate-500">
        Primary display uses <strong>deep</strong> normalized score when present; otherwise{' '}
        <strong>light</strong> (same precedence as API / TD-PERSISTENCE-008).
      </p>
      {overall ? (
        <p className="text-slate-800">
          Overall:{' '}
          {overall.value != null ? (
            <>
              <span className="font-mono text-lg">{Number(overall.value).toFixed(2)}</span>
              {overall.type ? (
                <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                  {overall.type}
                </span>
              ) : null}
            </>
          ) : (
            <span className="text-slate-400">—</span>
          )}
        </p>
      ) : (
        <p className="text-slate-500">No overall score block.</p>
      )}
      {criteria.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-md border border-slate-100 text-sm">
          {criteria.map((c) => (
            <li key={`${c.source}-${c.name}`} className="flex flex-wrap items-baseline gap-x-2 px-3 py-2">
              <span className="font-medium text-slate-800">{c.name}</span>
              <span className="text-xs text-slate-500">{c.source}</span>
              <span className="ml-auto font-mono text-slate-700">
                {c.score != null ? c.score.toFixed(2) : '—'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function ProfileSnippet({ profile }: { profile: CandidateProfile | undefined }) {
  if (!profile) return null
  const headline = profile.roles?.[0] ?? ''
  const meta = [
    profile.seniority ? String(profile.seniority) : null,
    profile.years_experience != null ? `${profile.years_experience}y` : null,
  ]
    .filter(Boolean)
    .join(' · ')
  const summary = profile.summary
  const skills = profile.skills ?? []
  if (!headline && !meta && !summary && skills.length === 0) return null
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Profile</h2>
      {headline ? <p className="mt-2 font-medium text-slate-800">{headline}</p> : null}
      {meta ? <p className="text-sm text-slate-600">{meta}</p> : null}
      {skills.length ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {skills.slice(0, 12).map((s) => (
            <span key={s} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
              {s}
            </span>
          ))}
        </div>
      ) : null}
      {summary ? <p className="mt-2 text-sm text-slate-600">{String(summary)}</p> : null}
    </section>
  )
}

function ScoringContextBlock({ sc }: { sc: Record<string, unknown> | null | undefined }) {
  if (!sc) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Scoring context</h2>
        <p className="text-sm text-slate-500">None active for this candidate.</p>
      </section>
    )
  }
  return (
    <section className="space-y-2 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Scoring context (read-only)</h2>
      <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-slate-500">Version</dt>
          <dd className="font-mono text-slate-900">{String(sc.context_version ?? '—')}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Status</dt>
          <dd className="text-slate-900">{String(sc.status ?? '—')}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Organization</dt>
          <dd className="text-slate-900">{sc.organization != null ? String(sc.organization) : '—'}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Job title</dt>
          <dd className="text-slate-900">{sc.job_title != null ? String(sc.job_title) : '—'}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-slate-500">Recruiter actor id</dt>
          <dd className="font-mono text-slate-900">
            {sc.recruiter_actor_id != null ? String(sc.recruiter_actor_id) : '—'}
          </dd>
        </div>
      </dl>
    </section>
  )
}

type DialogState = { open: false } | { open: true; action: RecruiterActionItem }

export function CandidateDetailPage() {
  const { candidateId = '' } = useParams()
  const queryClient = useQueryClient()
  const [dialog, setDialog] = useState<DialogState>({ open: false })
  const [reason, setReason] = useState('')
  const [actorId, setActorId] = useState(
    () => import.meta.env.VITE_DEFAULT_ACTOR_ID ?? 'recruiter-spa',
  )
  const [formError, setFormError] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['candidate', candidateId],
    queryFn: () => getCandidate(candidateId),
    enabled: Boolean(candidateId),
  })

  const mutation = useMutation({
    mutationFn: async ({ eventType, payload }: { eventType: string; payload: Record<string, unknown> }) =>
      postCandidateAction(candidateId, eventType, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['candidate', candidateId] })
      await queryClient.invalidateQueries({ queryKey: ['candidates'] })
      setDialog({ open: false })
      setReason('')
      setFormError(null)
    },
  })

  const openAction = (action: RecruiterActionItem) => {
    setFormError(null)
    setReason('')
    setActorId(import.meta.env.VITE_DEFAULT_ACTOR_ID ?? 'recruiter-spa')
    setDialog({ open: true, action })
  }

  const submitAction = async () => {
    if (!dialog.open) return
    const r = reason.trim()
    if (r.length < 1) {
      setFormError('Reason is required (min 1 character).')
      return
    }
    const aid = actorId.trim()
    if (aid.length < 1) {
      setFormError('Actor id is required.')
      return
    }
    setFormError(null)
    try {
      await mutation.mutateAsync({
        eventType: dialog.action.event_type,
        payload: {
          actor_id: aid,
          actor_type: 'recruiter',
          reason: r,
          evidence_refs: [],
        },
      })
    } catch (e) {
      if (e instanceof ApiRequestError) {
        const parsed = extractApiError(e.body)
        setFormError(parsed?.code ? `${parsed.code}: ${parsed.message ?? ''}` : e.message)
      } else {
        setFormError(e instanceof Error ? e.message : 'Request failed')
      }
    }
  }

  const grouped = q.data ? actionsByGroup(q.data.available_actions ?? []) : []

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm font-medium text-indigo-700 hover:underline">
          ← Back to list
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">Candidate</h1>
        <p className="mt-1 font-mono text-sm text-slate-600">{candidateId}</p>
      </div>

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
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Pipeline</h2>
            <p className="mt-2 text-slate-800">
              Stage: <span className="font-medium">{q.data.stage}</span>
            </p>
            <p className="text-slate-800">
              Status: <span className="font-medium">{q.data.status.kind}</span>
            </p>
            <p className="mt-3 text-sm text-slate-600">{q.data.summary}</p>
          </section>

          <ProfileSnippet profile={q.data.profile} />
          <ScoreBlock scores={q.data.scores} />
          <ScoringContextBlock sc={q.data.scoring_context as Record<string, unknown> | null | undefined} />

          <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Recruiter actions</h2>
            <p className="text-xs text-slate-500">
              Labels and availability come from the API only (TD-API-007).
            </p>
            {grouped.length === 0 ? (
              <p className="text-sm text-slate-500">No actions available in this state.</p>
            ) : (
              grouped.map(({ group, actions }) => (
                <div key={group} className="space-y-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{group}</h3>
                  <div className="flex flex-wrap gap-2">
                    {actions.map((a) => {
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
                          onClick={() => openAction(a)}
                        >
                          {a.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))
            )}
          </section>
        </>
      )}

      {dialog.open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="presentation"
          onClick={() => !mutation.isPending && setDialog({ open: false })}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="action-dialog-title"
            className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="action-dialog-title" className="text-lg font-semibold text-slate-900">
              {dialog.action.label}
            </h2>
            <p className="mt-1 font-mono text-xs text-slate-500">{dialog.action.event_type}</p>

            <div className="mt-4 space-y-3">
              <label className="block text-sm font-medium text-slate-700">
                Reason (required)
                <textarea
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm"
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Human justification for audit trail"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Actor id
                <input
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm"
                  value={actorId}
                  onChange={(e) => setActorId(e.target.value)}
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
                disabled={mutation.isPending}
                onClick={() => setDialog({ open: false })}
              >
                Cancel
              </button>
              <button
                type="button"
                className={
                  isDestructiveAction(dialog.action)
                    ? 'rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:opacity-50'
                    : 'rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50'
                }
                disabled={mutation.isPending}
                onClick={() => void submitAction()}
              >
                {mutation.isPending ? 'Submitting…' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
