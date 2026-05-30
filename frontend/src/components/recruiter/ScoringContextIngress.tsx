import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
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
import type { ChecklistScrollTarget } from '@/components/recruiter/ScoringReadinessChecklist'

type Dimension = 'organization' | 'recruiter_actor' | 'job'
type DimState = 'empty_locked' | 'editing' | 'saved_locked'

const DIMENSION_LABEL: Record<Dimension, string> = {
  organization: 'Describe Your Organization',
  recruiter_actor: 'Describe Your Preferences',
  job: "Describe Who You're Hiring",
}

const SECTION_IDS: Record<Dimension | 'materialized', string> = {
  organization: 'scoring-dim-organization',
  recruiter_actor: 'scoring-dim-recruiter',
  job: 'scoring-dim-job',
  materialized: 'scoring-dim-materialized',
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

function serverTextForDim(ctx: ScoringContextResponse, dim: Dimension): string {
  if (dim === 'organization') return ctx.organization_authoring_text ?? ''
  if (dim === 'recruiter_actor') return ctx.recruiter_actor_authoring_text ?? ''
  return ctx.job_authoring_text ?? ''
}

function dimInlineLabel(
  dim: Dimension,
  state: DimState,
  opts: { saving: boolean; fromPdf: boolean },
): string | null {
  if (opts.saving) return 'Saving…'
  if (state === 'editing') return 'Needs confirm'
  if (state === 'saved_locked') {
    if (dim === 'job' && opts.fromPdf) return 'From PDF'
    return 'Saved'
  }
  return null
}

type ScoringContextIngressProps = {
  context: ScoringContextResponse | undefined
  isLoading: boolean
  isError: boolean
  errorMessage?: string
  scrollToTarget?: ChecklistScrollTarget | null
  onScrollComplete?: () => void
}

export function ScoringContextIngress({
  context,
  isLoading,
  isError,
  errorMessage,
  scrollToTarget,
  onScrollComplete,
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
  const [busyDim, setBusyDim] = useState<Dimension | 'job_pdf' | null>(null)
  const [dimFormErrors, setDimFormErrors] = useState<Partial<Record<Dimension | 'job_pdf', string>>>(
    {},
  )
  const dimStateRef = useRef(dimState)
  dimStateRef.current = dimState

  useEffect(() => {
    if (!context) return
    setDimState((prev) => ({
      organization:
        prev.organization === 'editing'
          ? prev.organization
          : context.organization_authoring_text?.trim()
            ? 'saved_locked'
            : 'empty_locked',
      recruiter_actor:
        prev.recruiter_actor === 'editing'
          ? prev.recruiter_actor
          : context.recruiter_actor_authoring_text?.trim()
            ? 'saved_locked'
            : 'empty_locked',
      job:
        prev.job === 'editing'
          ? prev.job
          : context.job_authoring_text?.trim()
            ? 'saved_locked'
            : 'empty_locked',
    }))
    setDrafts((prev) => ({
      organization:
        dimStateRef.current.organization === 'editing'
          ? prev.organization
          : (context.organization_authoring_text ?? ''),
      recruiter_actor:
        dimStateRef.current.recruiter_actor === 'editing'
          ? prev.recruiter_actor
          : (context.recruiter_actor_authoring_text ?? ''),
      job:
        dimStateRef.current.job === 'editing' ? prev.job : (context.job_authoring_text ?? ''),
    }))
  }, [context])

  useEffect(() => {
    if (!scrollToTarget) return
    const id = SECTION_IDS[scrollToTarget]
    const el = document.getElementById(id)
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    onScrollComplete?.()
  }, [scrollToTarget, onScrollComplete])

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
      if (!serverProseComplete(latest)) {
        return
      }
      try {
        await refreshScoringContext()
        await invalidateContext()
      } catch {
        // Materialization failures surface via GET materialization_blockers on checklist.
      }
    },
    [invalidateContext, queryClient],
  )

  const cancelEditing = (dim: Dimension) => {
    if (!context) {
      setDrafts((d) => ({ ...d, [dim]: '' }))
      setDimState((s) => ({ ...s, [dim]: 'empty_locked' }))
    } else {
      const serverText = serverTextForDim(context, dim)
      if (serverText.trim()) {
        setDrafts((d) => ({ ...d, [dim]: serverText }))
        setDimState((s) => ({ ...s, [dim]: 'saved_locked' }))
      } else {
        setDrafts((d) => ({ ...d, [dim]: '' }))
        setDimState((s) => ({ ...s, [dim]: 'empty_locked' }))
      }
    }
    setDimFormErrors((e) => ({ ...e, [dim]: undefined }))
  }

  const confirmDimension = async (dim: Dimension) => {
    setDimFormErrors((e) => ({ ...e, [dim]: undefined }))
    setBusyDim(dim)
    try {
      const text = drafts[dim].trim()
      if (!text) {
        setDimFormErrors((e) => ({ ...e, [dim]: 'Text is required to confirm this dimension.' }))
        return
      }
      if (dim === 'organization') await postOrganizationContext(text)
      else if (dim === 'recruiter_actor') await postRecruiterActorContext(text)
      else await postJobContextText(text)
      await maybeRefreshAfterPersist(dim)
    } catch (e) {
      setDimFormErrors((err) => ({
        ...err,
        [dim]: e instanceof Error ? e.message : 'Context update failed',
      }))
    } finally {
      setBusyDim(null)
      await invalidateContext()
    }
  }

  const confirmJobPdf = async () => {
    setDimFormErrors((e) => ({ ...e, job_pdf: undefined, job: undefined }))
    if (!jobPdfFile) {
      setDimFormErrors((e) => ({ ...e, job_pdf: 'Choose a PDF file before confirming.' }))
      return
    }
    setBusyDim('job_pdf')
    try {
      const buf = await jobPdfFile.arrayBuffer()
      const bytes = new Uint8Array(buf)
      let binary = ''
      for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]!)
      await postJobContextPdf(btoa(binary), jobPdfFile.name)
      setJobPdfFile(null)
      await maybeRefreshAfterPersist('job')
    } catch (e) {
      setDimFormErrors((err) => ({
        ...err,
        job_pdf: e instanceof Error ? e.message : 'PDF upload failed',
      }))
    } finally {
      setBusyDim(null)
      await invalidateContext()
    }
  }

  const deleteDimension = async (dim: Dimension) => {
    setDimFormErrors((e) => ({ ...e, [dim]: undefined }))
    setBusyDim(dim)
    try {
      if (dim === 'organization') await clearOrganizationContext()
      else if (dim === 'recruiter_actor') await clearRecruiterActorContext()
      else await clearJobContext()
      setDimState((s) => ({ ...s, [dim]: 'empty_locked' }))
      setDrafts((d) => ({ ...d, [dim]: '' }))
      if (dim === 'job') setJobPdfFile(null)
    } catch (e) {
      setDimFormErrors((err) => ({
        ...err,
        [dim]: e instanceof Error ? e.message : 'Clear failed',
      }))
    } finally {
      setBusyDim(null)
      await invalidateContext()
    }
  }

  const jobUsesPdfPath = jobPdfFile !== null || (context != null && jobPdfSource(context))
  const globalBusy = busyDim !== null

  const renderDimensionHeader = (dim: Dimension, state: DimState) => {
    const saving = busyDim === dim
    const fromPdf = dim === 'job' && context != null && jobPdfSource(context)
    const inline = dimInlineLabel(dim, state, { saving, fromPdf })
    const dimError = dimFormErrors[dim]

    return (
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="text-sm font-medium text-slate-700">{DIMENSION_LABEL[dim]}</label>
        <div className="flex flex-wrap items-center gap-2">
          {inline ? (
            <span
              className={`inline-flex items-center gap-1 text-xs font-medium ${
                inline === 'From PDF'
                  ? 'text-emerald-800'
                  : inline === 'Needs confirm'
                    ? 'text-amber-800'
                    : inline === 'Saving…'
                      ? 'text-slate-600'
                      : 'text-emerald-800'
              }`}
            >
              {inline === 'Saved' || inline === 'From PDF' ? '✓' : null}
              {inline}
            </span>
          ) : null}
          {dimError ? (
            <span className="max-w-[14rem] text-xs text-red-700" role="alert">
              {dimError}
            </span>
          ) : null}
        </div>
      </div>
    )
  }

  const renderDimension = (dim: Dimension) => {
    const state = dimState[dim]
    const locked = state !== 'editing'
    const hideJobTextConfirm = dim === 'job' && jobUsesPdfPath

    return (
      <div
        key={dim}
        id={SECTION_IDS[dim]}
        className="scroll-mt-4 space-y-2 rounded-md border border-slate-100 bg-slate-50/50 p-3"
      >
        {renderDimensionHeader(dim, state)}
        <textarea
          className="min-h-[88px] w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm disabled:bg-slate-100"
          value={drafts[dim]}
          onChange={(e) => setDrafts((d) => ({ ...d, [dim]: e.target.value }))}
          disabled={locked || globalBusy}
        />
        <div className="flex flex-wrap gap-2">
          {state === 'empty_locked' && (
            <button
              type="button"
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
              disabled={globalBusy}
              onClick={() => setDimState((s) => ({ ...s, [dim]: 'editing' }))}
            >
              Create
            </button>
          )}
          {state === 'editing' && (
            <>
              <button
                type="button"
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                disabled={globalBusy || hideJobTextConfirm}
                onClick={() => void confirmDimension(dim)}
              >
                Confirm
              </button>
              <button
                type="button"
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                disabled={globalBusy}
                onClick={() => cancelEditing(dim)}
              >
                Cancel
              </button>
            </>
          )}
          {state === 'saved_locked' && (
            <>
              <button
                type="button"
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                disabled={globalBusy}
                onClick={() => setDimState((s) => ({ ...s, [dim]: 'editing' }))}
              >
                Edit
              </button>
              <button
                type="button"
                className="rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-red-100 disabled:opacity-50"
                disabled={globalBusy}
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

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Confirm each section. When all three are saved on the server, the last Confirm triggers
        refresh automatically.
      </p>
      {isLoading && <p className="text-sm text-slate-500">Loading scoring context…</p>}
      {isError && (
        <p className="text-sm text-red-700" role="alert">
          {errorMessage ?? 'Failed to load scoring context'}
        </p>
      )}
      <div className="space-y-4">
        {renderDimension('organization')}
        {renderDimension('recruiter_actor')}
        {renderDimension('job')}
        <div
          id={SECTION_IDS.materialized}
          className="scroll-mt-4 space-y-2 rounded-md border border-slate-100 bg-slate-50/50 p-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="text-sm font-medium text-slate-700">Upload Job Description</label>
            {jobPdfFile ? (
              <span className="text-xs font-medium text-amber-800">Needs confirm</span>
            ) : context && jobPdfSource(context) ? (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-800">
                ✓ From PDF
              </span>
            ) : null}
          </div>
          <p className="text-xs text-slate-500">
            Choose a PDF, then Confirm to extract job text. You can upload without opening the text
            editor first.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex cursor-pointer items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50">
              Choose file
              <input
                type="file"
                accept="application/pdf,.pdf"
                className="sr-only"
                disabled={globalBusy}
                onChange={(e) => setJobPdfFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <button
              type="button"
              className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              disabled={globalBusy || !jobPdfFile}
              onClick={() => void confirmJobPdf()}
            >
              {busyDim === 'job_pdf' ? 'Saving…' : 'Confirm'}
            </button>
          </div>
          {jobPdfFile && (
            <p className="text-xs text-slate-600">Selected: {jobPdfFile.name} (not uploaded yet)</p>
          )}
          {dimFormErrors.job_pdf ? (
            <p className="text-xs text-red-700" role="alert">
              {dimFormErrors.job_pdf}
            </p>
          ) : null}
        </div>
      </div>
      <details className="rounded-md border border-slate-200 bg-slate-50/80">
        <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-slate-700">
          Processed scoring context (debug)
        </summary>
        <div className="border-t border-slate-200 p-2">
          <ScoringContextPanel sc={context ?? null} title="" />
        </div>
      </details>
    </div>
  )
}

export function parseRefreshBlockers(err: unknown): string[] {
  const parsed = extractApiError(err)
  if (!parsed?.message) return ['Materialization failed']
  const match = parsed.message.match(/blockers:\s*(.+)$/i)
  if (match?.[1]) {
    return match[1]
      .split(';')
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return [parsed.message]
}
