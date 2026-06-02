import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ScoringContextResponse } from '@/api/types'
import {
  clearJobContext,
  clearOrganizationContext,
  clearRecruiterActorContext,
  getScoringContext,
  postJobContextPdf,
  postJobContextStructured,
  postJobContextText,
  postOrganizationContext,
  postOrganizationContextStructured,
  postRecruiterActorContext,
  postRecruiterActorContextStructured,
  refreshScoringContext,
} from '@/api/client'
import { ConfirmReplaceFormModal } from '@/components/recruiter/ConfirmReplaceFormModal'
import { ProseContextModal } from '@/components/recruiter/ProseContextModal'
import { ScoringContextPanel } from '@/components/recruiter/ScoringContextPanel'
import { StructuredContextFormModal } from '@/components/recruiter/StructuredContextFormModal'
import type { ChecklistScrollTarget } from '@/components/recruiter/ScoringReadinessChecklist'
import type { Dimension } from '@/lib/scoringContextFormSchemas'
import {
  defaultJobForm,
  defaultOrganizationForm,
  defaultRecruiterActorForm,
  joinTagsAsNewlines,
  parseJobContext,
  parseOrganizationContext,
  parseRecruiterActorContext,
  type JobFormValues,
  type OrganizationFormValues,
  type RecruiterActorFormValues,
} from '@/lib/scoringContextFormSchemas'

type DimState = 'empty_locked' | 'saved_locked'
type ModalKind = 'prose' | 'form' | 'confirm_replace'

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

function hasFormSourceRef(ctx: ScoringContextResponse | undefined, dim: Dimension): boolean {
  const needle =
    dim === 'organization'
      ? 'form://organization'
      : dim === 'recruiter_actor'
        ? 'form://recruiter_actor'
        : 'form://job'
  return (ctx?.source_refs ?? []).some((r) => r === needle)
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
  const [jobPdfFile, setJobPdfFile] = useState<File | null>(null)
  const [busyKey, setBusyKey] = useState<Dimension | 'job_pdf' | 'modal' | null>(null)

  const [modalKind, setModalKind] = useState<ModalKind | null>(null)
  const [modalDim, setModalDim] = useState<Dimension>('organization')
  const [proseDraft, setProseDraft] = useState('')
  const [proseError, setProseError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const [orgForm, setOrgForm] = useState<OrganizationFormValues>(defaultOrganizationForm())
  const [recForm, setRecForm] = useState<RecruiterActorFormValues>(defaultRecruiterActorForm())
  const [jobForm, setJobForm] = useState<JobFormValues>(defaultJobForm())

  useEffect(() => {
    if (!context) return
    setDimState({
      organization: context.organization_authoring_text?.trim() ? 'saved_locked' : 'empty_locked',
      recruiter_actor: context.recruiter_actor_authoring_text?.trim() ? 'saved_locked' : 'empty_locked',
      job: context.job_authoring_text?.trim() ? 'saved_locked' : 'empty_locked',
    })
  }, [context])

  useEffect(() => {
    if (!scrollToTarget) return
    const id = SECTION_IDS[scrollToTarget]
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
      if (!serverProseComplete(latest)) return
      try {
        await refreshScoringContext()
        await invalidateContext()
      } catch {
        // Materialization failures surface via GET materialization_blockers on checklist.
      }
    },
    [invalidateContext, queryClient],
  )

  const closeModal = () => {
    setModalKind(null)
    setProseError(null)
    setFormError(null)
    setBusyKey(null)
  }

  const openProseModal = (dim: Dimension) => {
    setModalDim(dim)
    setProseError(null)
    setFormError(null)
    if (hasFormSourceRef(context, dim)) {
      setModalKind('confirm_replace')
      return
    }
    setProseDraft(context ? serverTextForDim(context, dim) : '')
    setModalKind('prose')
  }

  const openFormModal = (dim: Dimension) => {
    setModalDim(dim)
    setProseError(null)
    setFormError(null)
    if (dim === 'organization') {
      const parsed = parseOrganizationContext(context?.organization_context)
      setOrgForm(parsed ?? defaultOrganizationForm())
    } else if (dim === 'recruiter_actor') {
      const parsed = parseRecruiterActorContext(context?.recruiter_actor_context)
      setRecForm(parsed ?? defaultRecruiterActorForm())
    } else {
      const parsed = parseJobContext(context?.job_context)
      setJobForm(parsed ?? defaultJobForm())
    }
    setModalKind('form')
  }

  const confirmProse = async (dim: Dimension, raw: string) => {
    setBusyKey('modal')
    setProseError(null)
    try {
      const text = String(raw || '').trim()
      if (!text) {
        setProseError('Text Is Required.')
        return
      }
      if (dim === 'organization') await postOrganizationContext(text)
      else if (dim === 'recruiter_actor') await postRecruiterActorContext(text)
      else await postJobContextText(text)
      await maybeRefreshAfterPersist(dim)
      closeModal()
    } catch (e) {
      setProseError(e instanceof Error ? e.message : 'Context Update Failed')
    } finally {
      await invalidateContext()
      setBusyKey(null)
    }
  }

  const confirmStructured = async (
    dim: Dimension,
    values: OrganizationFormValues | RecruiterActorFormValues | JobFormValues,
  ) => {
    setBusyKey('modal')
    setFormError(null)
    try {
      if (dim === 'organization') {
        const v = values as OrganizationFormValues
        await postOrganizationContextStructured({
          company_name: v.company_name,
          industry: v.industry || undefined,
          team_name: v.team_name || undefined,
          environment_signals: v.environment_signals,
          preference_signals: v.preference_signals,
          summary: v.summary || undefined,
          source_ref: 'form://organization',
        })
      } else if (dim === 'recruiter_actor') {
        const v = values as RecruiterActorFormValues
        await postRecruiterActorContextStructured({
          actor_id: v.actor_id,
          actor_role: v.actor_role || undefined,
          preference_signals: v.preference_signals,
          avoid_signals: v.avoid_signals,
          source_ref: 'form://recruiter_actor',
        })
      } else {
        const v = values as JobFormValues
        await postJobContextStructured({
          role_title: v.role_title,
          must_haves_answer: joinTagsAsNewlines(v.must_haves),
          preferred_answer: joinTagsAsNewlines(v.nice_to_have),
          success_answer: joinTagsAsNewlines(v.success),
          responsibilities_answer: joinTagsAsNewlines(v.responsibilities),
          source_ref: 'form://job',
        })
      }
      await maybeRefreshAfterPersist(dim)
      closeModal()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Form Save Failed')
    } finally {
      await invalidateContext()
      setBusyKey(null)
    }
  }

  const confirmJobPdf = async () => {
    setFormError(null)
    if (!jobPdfFile) {
      setFormError('Choose A PDF File Before Confirming.')
      return
    }
    setBusyKey('job_pdf')
    try {
      const buf = await jobPdfFile.arrayBuffer()
      const bytes = new Uint8Array(buf)
      let binary = ''
      for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]!)
      await postJobContextPdf(btoa(binary), jobPdfFile.name)
      setJobPdfFile(null)
      await maybeRefreshAfterPersist('job')
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'PDF Upload Failed')
    } finally {
      await invalidateContext()
      setBusyKey(null)
    }
  }

  const deleteDimension = async (dim: Dimension) => {
    setFormError(null)
    setBusyKey(dim)
    try {
      if (dim === 'organization') await clearOrganizationContext()
      else if (dim === 'recruiter_actor') await clearRecruiterActorContext()
      else await clearJobContext()
      setDimState((s) => ({ ...s, [dim]: 'empty_locked' }))
      if (dim === 'job') setJobPdfFile(null)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Clear Failed')
    } finally {
      await invalidateContext()
      setBusyKey(null)
    }
  }

  const globalBusy = busyKey !== null
  const fromPdf = context != null && jobPdfSource(context)

  const structuredPrefillOk = useMemo(() => {
    if (!context) return { organization: false, recruiter_actor: false, job: false }
    return {
      organization: parseOrganizationContext(context.organization_context) !== null,
      recruiter_actor: parseRecruiterActorContext(context.recruiter_actor_context) !== null,
      job: parseJobContext(context.job_context) !== null,
    }
  }, [context])

  const renderDimension = (dim: Dimension) => {
    const state = dimState[dim]
    const saved = state === 'saved_locked'
    const saving = busyKey === dim
    const viaForm = hasFormSourceRef(context, dim)
    const headerStatus = saving
      ? 'Saving…'
      : saved
        ? dim === 'job' && fromPdf
          ? 'From PDF'
          : 'Saved'
        : 'Not Saved'
    const canEditForm = structuredPrefillOk[dim]
    const editFormDisabledHint =
      saved && !canEditForm ? 'Use Edit For Text, Or Fill The Form To Add Structured Fields.' : null

    return (
      <div
        key={dim}
        id={SECTION_IDS[dim]}
        className={`scroll-mt-4 space-y-3 rounded-md border p-4 ${
          saved ? 'border-emerald-300 bg-emerald-50/80' : 'border-slate-200 bg-white'
        }`}
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            {saved ? (
              <span
                className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-200 text-xs text-emerald-900"
                aria-label="Saved"
              >
                ✓
              </span>
            ) : null}
            <h3 className="text-sm font-semibold text-slate-900">{DIMENSION_LABEL[dim]}</h3>
          </div>
          <span className={`text-xs font-medium ${saved ? 'text-emerald-900' : 'text-slate-600'}`}>
            {headerStatus}
          </span>
        </div>

        {saved && context ? (
          <p className="text-xs text-slate-700">
            {viaForm ? (
              <span className="font-medium">Saved Via Form</span>
            ) : (
              <span>{serverTextForDim(context, dim).split('\n')[0]?.slice(0, 120) || 'Saved'}</span>
            )}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
            disabled={globalBusy}
            onClick={() => openProseModal(dim)}
          >
            {saved ? 'Edit' : 'Describe'}
          </button>
          <span className="mx-1 text-xs font-semibold text-slate-500">Or</span>
          <button
            type="button"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
            disabled={globalBusy}
            onClick={() => openFormModal(dim)}
          >
            {saved ? 'Edit The Form' : 'Fill The Form'}
          </button>
          {saved ? (
            <button
              type="button"
              className="ml-auto rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-800 hover:bg-red-100 disabled:opacity-50"
              disabled={globalBusy}
              onClick={() => void deleteDimension(dim)}
            >
              Delete
            </button>
          ) : null}
        </div>

        {saved && !canEditForm ? <p className="text-xs italic text-slate-600">{editFormDisabledHint}</p> : null}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Confirm each section. When all three are saved on the server, the last Confirm triggers refresh
        automatically.
      </p>
      {isLoading ? <p className="text-sm text-slate-500">Loading scoring context…</p> : null}
      {isError ? (
        <p className="text-sm text-red-700" role="alert">
          {errorMessage ?? 'Failed to load scoring context'}
        </p>
      ) : null}
      {formError ? (
        <p className="text-sm text-red-700" role="alert">
          {formError}
        </p>
      ) : null}

      <div className="space-y-4">
        {renderDimension('organization')}
        {renderDimension('recruiter_actor')}
        <div className="space-y-3">
          {renderDimension('job')}
          <div id={SECTION_IDS.materialized} className="scroll-mt-4 space-y-2 rounded-md border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="text-sm font-medium text-slate-800">Upload Job Description</label>
              {jobPdfFile ? (
                <span className="text-xs font-medium text-amber-800">Needs Confirm</span>
              ) : fromPdf ? (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-800">✓ From PDF</span>
              ) : null}
            </div>
            <p className="text-xs text-slate-500">Choose A PDF, Then Confirm To Extract Job Text.</p>
            <div className="flex flex-wrap items-center gap-2">
              <label className="inline-flex cursor-pointer items-center rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50">
                Choose File
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
                className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                disabled={globalBusy || !jobPdfFile}
                onClick={() => void confirmJobPdf()}
              >
                {busyKey === 'job_pdf' ? 'Saving…' : 'Confirm'}
              </button>
            </div>
            {jobPdfFile ? <p className="text-xs text-slate-600">Selected: {jobPdfFile.name} (Not Uploaded Yet)</p> : null}
          </div>
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

      <ConfirmReplaceFormModal
        open={modalKind === 'confirm_replace'}
        onCancel={closeModal}
        onConfirm={() => {
          setProseDraft(context ? serverTextForDim(context, modalDim) : '')
          setModalKind('prose')
        }}
      />
      <ProseContextModal
        open={modalKind === 'prose'}
        title={DIMENSION_LABEL[modalDim]}
        initialText={proseDraft}
        isSaving={busyKey === 'modal'}
        error={proseError}
        onCancel={closeModal}
        onConfirm={(t) => void confirmProse(modalDim, t)}
      />
      <StructuredContextFormModal
        open={modalKind === 'form'}
        dim={modalDim}
        title={dimState[modalDim] === 'saved_locked' ? 'Edit The Form' : 'Fill The Form'}
        initialValues={modalDim === 'organization' ? orgForm : modalDim === 'recruiter_actor' ? recForm : jobForm}
        disableEditHint={
          dimState[modalDim] === 'saved_locked' && !structuredPrefillOk[modalDim]
            ? 'Use Edit For Text, Or Fill The Form To Add Structured Fields.'
            : null
        }
        isSaving={busyKey === 'modal'}
        error={formError}
        onCancel={closeModal}
        onConfirm={(v) => void confirmStructured(modalDim, v)}
      />
    </div>
  )
}
