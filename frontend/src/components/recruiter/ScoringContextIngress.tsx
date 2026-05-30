import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import type { ScoringContextResponse } from '@/api/types'
import {
  clearJobContext,
  clearOrganizationContext,
  clearRecruiterActorContext,
  extractApiError,
  getScoringContext,
  postJobContextPdf,
  postJobContextText,
  postOrganizationContext,
  postRecruiterActorContext,
  refreshScoringContext,
} from '@/api/client'
import { ScoringContextPanel } from '@/components/recruiter/ScoringContextPanel'

type Dimension = 'organization' | 'recruiter_actor' | 'job'
type DimState = 'empty_locked' | 'editing' | 'saved_locked'

const DIMENSION_LABEL: Record<Dimension, string> = {
  organization: 'Organization',
  recruiter_actor: 'Recruiter actor',
  job: 'Job',
}

function serverProseComplete(ctx: ScoringContextResponse): boolean {
  return !!(
    ctx.organization_authoring_text?.trim() &&
    ctx.recruiter_actor_authoring_text?.trim() &&
    ctx.job_authoring_text?.trim()
  )
}

function jobPdfSource(ctx: ScoringContextResponse): boolean {
  return (ctx.source_refs ?? []).some((ref) => ref.startsWith('pdf://'))
}

function parseRefreshBlockers(err: unknown): string[] {
  const parsed = extractApiError(err)
  if (!parsed?.message) return ['Materialization failed']
  const match = parsed.message.match(/blockers:\s*(.+)$/i)
  if (match?.[1]) {
    return match[1].split(';').map((s) => s.trim()).filter(Boolean)
  }
  return [parsed.message]
}

type ScoringContextIngressProps = {
  context: ScoringContextResponse | undefined
  isLoading: boolean
  isError: boolean
  errorMessage?: string
}

export function ScoringContextIngress({
  context,
  isLoading,
  isError,
  errorMessage,
}: ScoringContextIngressProps) {
  const queryClient = useQueryClient()
  const [dimState, setDimState] = useState<Record<Dimension, DimState>>({
    organization: 'empty_locked',
    recruiter_actor: 'empty_locked',
    job: 'empty_locked',
  })
  const [drafts, setDrafts] = useState<Record<Dimension, string>>({
    organization: '',
    recruiter_actor: '',
    job: '',
  })
  const [jobPdfFile, setJobPdfFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [warnMsg, setWarnMsg] = useState<string | null>(null)
  const [blockers, setBlockers] = useState<string[]>([])

  useEffect(() => {
    if (!context) return
    setDimState({
      organization: context.organization_authoring_text?.trim() ? 'saved_locked' : 'empty_locked',
      recruiter_actor: context.recruiter_actor_authoring_text?.trim()
        ? 'saved_locked'
        : 'empty_locked',
      job: context.job_authoring_text?.trim() ? 'saved_locked' : 'empty_locked',
    })
    setDrafts({
      organization: context.organization_authoring_text ?? '',
      recruiter_actor: context.recruiter_actor_authoring_text ?? '',
      job: context.job_authoring_text ?? '',
    })
  }, [context])

  const invalidateContext = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['scoring-context'] })
    await queryClient.invalidateQueries({ queryKey: ['candidates'] })
  }, [queryClient])

  const maybeRefreshAfterPersist = useCallback(
    async (dim: Dimension) => {
      const latest = await queryClient.fetchQuery({
        queryKey: ['scoring-context'],
        queryFn: getScoringContext,
      })
      setDimState((s) => ({ ...s, [dim]: 'saved_locked' }))
      setSuccessMsg('Saved successfully.')
      setWarnMsg(null)
      setBlockers([])
      if (!serverProseComplete(latest)) {
        setWarnMsg(
          'Saved. Confirm the remaining dimensions before scoring context can refresh to ready.',
        )
        return
      }
      try {
        const readyCtx = await refreshScoringContext()
        await invalidateContext()
        if (readyCtx.status === 'ready') {
          setSuccessMsg('Saved successfully. Scoring context is ready.')
        }
      } catch (e) {
        setBlockers(parseRefreshBlockers(e))
      }
    },
    [invalidateContext, queryClient],
  )

  const confirmDimension = async (dim: Dimension) => {
    setFormError(null)
    setSuccessMsg(null)
    setWarnMsg(null)
    setBlockers([])
    setBusy(true)
    try {
      if (dim === 'job' && jobPdfFile) {
        const buf = await jobPdfFile.arrayBuffer()
        const bytes = new Uint8Array(buf)
        let binary = ''
        for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]!)
        await postJobContextPdf(btoa(binary), jobPdfFile.name)
        setJobPdfFile(null)
      } else {
        const text = drafts[dim].trim()
        if (!text) {
          setFormError('Text is required to confirm this dimension.')
          return
        }
        if (dim === 'organization') await postOrganizationContext(text)
        else if (dim === 'recruiter_actor') await postRecruiterActorContext(text)
        else await postJobContextText(text)
      }
      await maybeRefreshAfterPersist(dim)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Context update failed')
    } finally {
      setBusy(false)
      await invalidateContext()
    }
  }

  const deleteDimension = async (dim: Dimension) => {
    setFormError(null)
    setSuccessMsg(null)
    setWarnMsg(null)
    setBlockers([])
    setBusy(true)
    try {
      if (dim === 'organization') await clearOrganizationContext()
      else if (dim === 'recruiter_actor') await clearRecruiterActorContext()
      else await clearJobContext()
      setDimState((s) => ({ ...s, [dim]: 'empty_locked' }))
      setDrafts((d) => ({ ...d, [dim]: '' }))
      if (dim === 'job') setJobPdfFile(null)
      setSuccessMsg('Dimension cleared.')
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Clear failed')
    } finally {
      setBusy(false)
      await invalidateContext()
    }
  }

  const renderDimension = (dim: Dimension) => {
    const state = dimState[dim]
    const locked = state !== 'editing'
    const showJobPdfHint =
      dim === 'job' && state === 'saved_locked' && context && jobPdfSource(context)

    return (
      <div key={dim} className="space-y-2 rounded-md border border-slate-100 bg-slate-50/50 p-3">
        <label className="block text-sm font-medium text-slate-700">
          {DIMENSION_LABEL[dim]} (text)
        </label>
        {showJobPdfHint && (
          <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            Job text extracted from PDF — use Edit to replace via text.
          </p>
        )}
        <textarea
          className="min-h-[88px] w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm disabled:bg-slate-100"
          value={drafts[dim]}
          onChange={(e) => setDrafts((d) => ({ ...d, [dim]: e.target.value }))}
          disabled={locked || busy}
        />
        <div className="flex flex-wrap gap-2">
          {state === 'empty_locked' && (
            <button
              type="button"
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
              disabled={busy}
              onClick={() => setDimState((s) => ({ ...s, [dim]: 'editing' }))}
            >
              Create
            </button>
          )}
          {state === 'editing' && (
            <button
              type="button"
              className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              disabled={busy}
              onClick={() => void confirmDimension(dim)}
            >
              Confirm
            </button>
          )}
          {state === 'saved_locked' && (
            <>
              <button
                type="button"
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                disabled={busy}
                onClick={() => setDimState((s) => ({ ...s, [dim]: 'editing' }))}
              >
                Edit
              </button>
              <button
                type="button"
                className="rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-red-100 disabled:opacity-50"
                disabled={busy}
                onClick={() => void deleteDimension(dim)}
              >
                Delete
              </button>
            </>
          )}
        </div>
      </div>
    )
  }

  const ready = context?.status === 'ready'

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Scoring context ingress</h2>
        <p className="mt-1 text-sm text-slate-600">
          Confirm each dimension in order. When all three are saved on the server, the last Confirm
          triggers refresh. Candidate PDF upload requires{' '}
          <code className="rounded bg-slate-100 px-1 text-xs">ready</code>.
        </p>
        {!ready && context && (
          <p
            className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
            role="status"
          >
            Scoring context is <strong>{context.status}</strong> — create candidate by PDF is blocked
            until ready.
          </p>
        )}
        {successMsg && (
          <p className="mt-3 text-sm text-emerald-800" role="status">
            {successMsg}
          </p>
        )}
        {warnMsg && (
          <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {warnMsg}
          </p>
        )}
        {blockers.length > 0 && (
          <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
            <p className="font-medium">Materialization blockers</p>
            <ul className="mt-1 list-inside list-disc">
              {blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </div>
        )}
        {formError && (
          <p className="mt-3 text-sm text-red-700" role="alert">
            {formError}
          </p>
        )}
        {isLoading && <p className="mt-3 text-sm text-slate-500">Loading scoring context…</p>}
        {isError && (
          <p className="mt-3 text-sm text-red-700" role="alert">
            {errorMessage ?? 'Failed to load scoring context'}
          </p>
        )}
        <div className="mt-4 space-y-4">
          {renderDimension('organization')}
          {renderDimension('recruiter_actor')}
          {renderDimension('job')}
          <div className="space-y-2 rounded-md border border-slate-100 bg-slate-50/50 p-3">
            <label className="block text-sm font-medium text-slate-700">Job (PDF)</label>
            <p className="text-xs text-slate-500">
              Choose a file, then Confirm on the Job dimension (upload runs on Confirm).
            </p>
            <label className="inline-flex cursor-pointer items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50">
              Choose file
              <input
                type="file"
                accept="application/pdf,.pdf"
                className="sr-only"
                disabled={busy || dimState.job === 'empty_locked'}
                onChange={(e) => setJobPdfFile(e.target.files?.[0] ?? null)}
              />
            </label>
            {jobPdfFile && (
              <p className="text-xs text-slate-600">Selected: {jobPdfFile.name} (not uploaded yet)</p>
            )}
          </div>
        </div>
        {context && context.materialization_blockers && context.materialization_blockers.length > 0 && (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-950">
            <p className="font-medium">Server materialization blockers</p>
            <ul className="mt-1 list-inside list-disc">
              {context.materialization_blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </div>
        )}
      </section>
      <ScoringContextPanel
        sc={context ?? null}
        title="Processed scoring context (full GET payload)"
      />
    </div>
  )
}
