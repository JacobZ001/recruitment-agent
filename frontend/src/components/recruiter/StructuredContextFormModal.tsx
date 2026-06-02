import { useEffect, useMemo, useState } from 'react'
import { ModalBase } from '@/components/recruiter/ModalBase'
import { TagInput } from '@/components/recruiter/TagInput'
import type { Dimension } from '@/lib/scoringContextFormSchemas'
import {
  defaultJobForm,
  defaultOrganizationForm,
  defaultRecruiterActorForm,
  type FieldErrorMap,
  type JobField,
  type JobFormValues,
  type OrganizationField,
  type OrganizationFormValues,
  type RecruiterActorField,
  type RecruiterActorFormValues,
  validateJobForm,
  validateOrganizationForm,
  validateRecruiterActorForm,
} from '@/lib/scoringContextFormSchemas'

type StructuredContextFormModalProps = {
  open: boolean
  dim: Dimension
  title: string
  initialValues: OrganizationFormValues | RecruiterActorFormValues | JobFormValues
  disableEditHint?: string | null
  isSaving: boolean
  error: string | null
  onCancel: () => void
  onConfirm: (values: OrganizationFormValues | RecruiterActorFormValues | JobFormValues) => void
}

function TextField({
  label,
  example,
  value,
  onChange,
  error,
}: {
  label: string
  example: string
  value: string
  onChange: (v: string) => void
  error?: string
}) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-slate-800">{label}</label>
      <p className="text-xs italic text-slate-500">
        <span className="font-medium not-italic">Example:</span> {example}
      </p>
      <input
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {error ? (
        <p className="text-xs font-medium text-red-700" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}

function TextAreaField({
  label,
  example,
  value,
  onChange,
  error,
}: {
  label: string
  example: string
  value: string
  onChange: (v: string) => void
  error?: string
}) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-slate-800">{label}</label>
      <p className="text-xs italic text-slate-500">
        <span className="font-medium not-italic">Example:</span> {example}
      </p>
      <textarea
        className="min-h-[92px] w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {error ? (
        <p className="text-xs font-medium text-red-700" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}

export function StructuredContextFormModal({
  open,
  dim,
  title,
  initialValues,
  disableEditHint,
  isSaving,
  error,
  onCancel,
  onConfirm,
}: StructuredContextFormModalProps) {
  const [org, setOrg] = useState<OrganizationFormValues>(defaultOrganizationForm())
  const [rec, setRec] = useState<RecruiterActorFormValues>(defaultRecruiterActorForm())
  const [job, setJob] = useState<JobFormValues>(defaultJobForm())

  const [orgErrors, setOrgErrors] = useState<FieldErrorMap<OrganizationField>>({})
  const [recErrors, setRecErrors] = useState<FieldErrorMap<RecruiterActorField>>({})
  const [jobErrors, setJobErrors] = useState<FieldErrorMap<JobField>>({})

  useEffect(() => {
    if (!open) return
    if (dim === 'organization') setOrg(initialValues as OrganizationFormValues)
    if (dim === 'recruiter_actor') setRec(initialValues as RecruiterActorFormValues)
    if (dim === 'job') setJob(initialValues as JobFormValues)
    setOrgErrors({})
    setRecErrors({})
    setJobErrors({})
  }, [open, dim, initialValues])

  const body = useMemo(() => {
    if (dim === 'organization') {
      return (
        <div className="space-y-5">
          <TextField
            label="Company Name"
            example="BlueOcean Recruitment"
            value={org.company_name}
            onChange={(v) => setOrg((p) => ({ ...p, company_name: v }))}
            error={orgErrors.company_name}
          />
          <TextField
            label="Industry"
            example="Recruitment"
            value={org.industry}
            onChange={(v) => setOrg((p) => ({ ...p, industry: v }))}
            error={orgErrors.industry}
          />
          <TextField
            label="Team Name"
            example="Talent Ops"
            value={org.team_name}
            onChange={(v) => setOrg((p) => ({ ...p, team_name: v }))}
            error={orgErrors.team_name}
          />
          <TagInput
            label="How Does Your Team Work?"
            example="Fast-paced recruiter workflow"
            tags={org.environment_signals}
            onChange={(next) => setOrg((p) => ({ ...p, environment_signals: next }))}
          />
          {orgErrors.environment_signals ? (
            <p className="text-xs font-medium text-red-700" role="alert">
              {orgErrors.environment_signals}
            </p>
          ) : null}
          <TagInput
            label="What Do You Value In Candidates?"
            example="Clear communication"
            tags={org.preference_signals}
            onChange={(next) => setOrg((p) => ({ ...p, preference_signals: next }))}
          />
          {orgErrors.preference_signals ? (
            <p className="text-xs font-medium text-red-700" role="alert">
              {orgErrors.preference_signals}
            </p>
          ) : null}
          <TextAreaField
            label="Short Summary (Optional)"
            example="Boutique recruitment firm focused on ops excellence."
            value={org.summary}
            onChange={(v) => setOrg((p) => ({ ...p, summary: v }))}
            error={orgErrors.summary}
          />
        </div>
      )
    }
    if (dim === 'recruiter_actor') {
      return (
        <div className="space-y-5">
          <TextField
            label="Your Name Or Recruiter ID"
            example="Jane-recruiter"
            value={rec.actor_id}
            onChange={(v) => setRec((p) => ({ ...p, actor_id: v }))}
            error={recErrors.actor_id}
          />
          <TextField
            label="Your Role (Optional)"
            example="Lead Recruiter"
            value={rec.actor_role}
            onChange={(v) => setRec((p) => ({ ...p, actor_role: v }))}
            error={recErrors.actor_role}
          />
          <TagInput
            label="What You Look For In Candidates"
            example="Ownership"
            tags={rec.preference_signals}
            onChange={(next) => setRec((p) => ({ ...p, preference_signals: next }))}
          />
          <TagInput
            label="What You Want To Avoid"
            example="Unclear communication"
            tags={rec.avoid_signals}
            onChange={(next) => setRec((p) => ({ ...p, avoid_signals: next }))}
          />
          {recErrors.preference_signals ? (
            <p className="text-xs font-medium text-red-700" role="alert">
              {recErrors.preference_signals}
            </p>
          ) : null}
        </div>
      )
    }
    return (
      <div className="space-y-5">
        <TextField
          label="Job Title"
          example="Recruiting Operations Specialist"
          value={job.role_title}
          onChange={(v) => setJob((p) => ({ ...p, role_title: v }))}
          error={jobErrors.role_title}
        />
        <TagInput
          label="Must-Haves"
          example="Stakeholder communication"
          tags={job.must_haves}
          onChange={(next) => setJob((p) => ({ ...p, must_haves: next }))}
        />
        {jobErrors.must_haves ? (
          <p className="text-xs font-medium text-red-700" role="alert">
            {jobErrors.must_haves}
          </p>
        ) : null}
        <TagInput
          label="Nice-To-Have (Optional)"
          example="ATS familiarity"
          tags={job.nice_to_have}
          onChange={(next) => setJob((p) => ({ ...p, nice_to_have: next }))}
        />
        <TagInput
          label="What Success Looks Like"
          example="Keep candidate flow organized"
          tags={job.success}
          onChange={(next) => setJob((p) => ({ ...p, success: next }))}
        />
        <TagInput
          label="Main Responsibilities"
          example="Coordinate interviews"
          tags={job.responsibilities}
          onChange={(next) => setJob((p) => ({ ...p, responsibilities: next }))}
        />
      </div>
    )
  }, [dim, job, jobErrors, org, orgErrors, rec, recErrors])

  const onSubmit = () => {
    if (dim === 'organization') {
      const errs = validateOrganizationForm(org)
      setOrgErrors(errs)
      if (Object.keys(errs).length > 0) return
      onConfirm(org)
      return
    }
    if (dim === 'recruiter_actor') {
      const errs = validateRecruiterActorForm(rec)
      setRecErrors(errs)
      if (Object.keys(errs).length > 0) return
      onConfirm(rec)
      return
    }
    const errs = validateJobForm(job)
    setJobErrors(errs)
    if (Object.keys(errs).length > 0) return
    onConfirm(job)
  }

  return (
    <ModalBase open={open} title={title} onClose={onCancel}>
      {disableEditHint ? (
        <p className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          {disableEditHint}
        </p>
      ) : null}
      {body}
      {error ? (
        <p className="mt-3 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
          disabled={isSaving}
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="button"
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          disabled={isSaving}
          onClick={onSubmit}
        >
          Confirm
        </button>
      </div>
    </ModalBase>
  )
}

