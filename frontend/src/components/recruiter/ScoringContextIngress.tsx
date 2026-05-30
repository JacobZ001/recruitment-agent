import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import type { ScoringContextResponse } from '@/api/types'
import {
  clearJobContext,
  clearOrganizationContext,
  clearRecruiterActorContext,
  postJobContextPdf,
  postJobContextText,
  postOrganizationContext,
  postRecruiterActorContext,
  refreshScoringContext,
} from '@/api/client'
import { ScoringContextPanel } from '@/components/recruiter/ScoringContextPanel'
import { NULL_DISPLAY } from '@/lib/format'

type Dimension = 'organization' | 'recruiter_actor' | 'job'

const DIMENSION_LABEL: Record<Dimension, string> = {
  organization: 'Organization',
  recruiter_actor: 'Recruiter actor',
  job: 'Job',
}

function authoringForDimension(ctx: ScoringContextResponse, dim: Dimension): string {
  if (dim === 'organization') return ctx.organization_authoring_text ?? ''
  if (dim === 'recruiter_actor') return ctx.recruiter_actor_authoring_text ?? ''
  return ctx.job_authoring_text ?? ''
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
  const [drafts, setDrafts] = useState<Record<Dimension, string>>({
    organization: '',
    recruiter_actor: '',
    job: '',
  })
  const [jobPdfName, setJobPdfName] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (!context) return
    setDrafts({
      organization: context.organization_authoring_text ?? '',
      recruiter_actor: context.recruiter_actor_authoring_text ?? '',
      job: context.job_authoring_text ?? '',
    })
  }, [context])

  const mutation = useMutation({
    mutationFn: async () => undefined,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scoring-context'] })
      void queryClient.invalidateQueries({ queryKey: ['candidates'] })
    },
  })

  const confirmDimension = useCallback(
    async (dim: Dimension) => {
      setFormError(null)
      const text = drafts[dim].trim()
      try {
        if (text) {
          if (dim === 'organization') await postOrganizationContext(text)
          else if (dim === 'recruiter_actor') await postRecruiterActorContext(text)
          else await postJobContextText(text)
          await refreshScoringContext()
        } else {
          if (dim === 'organization') await clearOrganizationContext()
          else if (dim === 'recruiter_actor') await clearRecruiterActorContext()
          else await clearJobContext()
        }
        await queryClient.invalidateQueries({ queryKey: ['scoring-context'] })
      } catch (e) {
        setFormError(e instanceof Error ? e.message : 'Context update failed')
      }
    },
    [drafts, queryClient],
  )

  const onJobPdfChange = async (file: File | null) => {
    if (!file) return
    setFormError(null)
    setJobPdfName(file.name)
    try {
      const buf = await file.arrayBuffer()
      const bytes = new Uint8Array(buf)
      let binary = ''
      for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]!)
      const pdf_base64 = btoa(binary)
      await postJobContextPdf(pdf_base64, file.name)
      await refreshScoringContext()
      await queryClient.invalidateQueries({ queryKey: ['scoring-context'] })
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Job PDF upload failed')
    }
  }

  const ready = context?.status === 'ready'

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Scoring context ingress</h2>
        <p className="mt-1 text-sm text-slate-600">
          Edit each dimension and click Confirm (upsert or clear + automatic refresh). Candidate
          PDF upload is enabled only when status is{' '}
          <code className="rounded bg-slate-100 px-1 text-xs">ready</code>.
        </p>
        {!ready && context && (
          <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">
            Scoring context is <strong>{context.status}</strong> — create candidate by PDF is
            blocked until ready.
          </p>
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
        <div className="mt-4 space-y-6">
          {(['organization', 'recruiter_actor', 'job'] as const).map((dim) => (
            <div key={dim} className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">
                {DIMENSION_LABEL[dim]} (text)
              </label>
              <textarea
                className="min-h-[88px] w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm"
                value={drafts[dim]}
                onChange={(e) => setDrafts((d) => ({ ...d, [dim]: e.target.value }))}
                disabled={mutation.isPending}
              />
              <button
                type="button"
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                disabled={mutation.isPending}
                onClick={() => void confirmDimension(dim)}
              >
                Confirm
              </button>
              {context && (
                <p className="text-xs text-slate-500">
                  Saved: {authoringForDimension(context, dim) || NULL_DISPLAY}
                </p>
              )}
            </div>
          ))}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-700">Job (PDF)</label>
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="block w-full text-sm text-slate-600"
              onChange={(e) => void onJobPdfChange(e.target.files?.[0] ?? null)}
            />
            {jobPdfName ? (
              <p className="text-xs text-slate-500">Last uploaded: {jobPdfName}</p>
            ) : null}
          </div>
        </div>
      </section>
      <ScoringContextPanel sc={context ?? null} title="Processed scoring context (full GET payload)" />
    </div>
  )
}
