import type { CandidateProfile } from '@/api/types'
import { ExpandableText } from '@/components/recruiter/ExpandableText'
import { NULL_DISPLAY, formatFieldLabel, formatScalar } from '@/lib/format'

function TagList({ items }: { items: string[] }) {
  if (!items.length) {
    return <span className="text-sm text-slate-400">{NULL_DISPLAY}</span>
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <li key={item}>
          <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium text-slate-800">
            {item}
          </span>
        </li>
      ))}
    </ul>
  )
}

const PROFILE_SCALAR_KEYS: (keyof NonNullable<CandidateProfile>)[] = [
  'headline',
  'primary_email',
  'primary_phone',
  'preferred_contact_method',
  'location',
  'timezone',
  'seniority',
  'years_experience',
  'work_authorization',
  'compensation_expectation',
  'availability_date',
]

const PROFILE_LIST_KEYS: (keyof NonNullable<CandidateProfile>)[] = [
  'languages',
  'skills',
  'industries',
  'roles',
  'external_profile_urls',
]

export function ProfilePane({ profile }: { profile: CandidateProfile | undefined }) {
  if (!profile) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Profile</h2>
        <p className="mt-2 text-sm text-slate-500">{NULL_DISPLAY}</p>
      </section>
    )
  }

  return (
    <section className="space-y-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Profile</h2>
      <div className="grid grid-cols-1 gap-x-8 gap-y-5 border-t border-slate-100 pt-5 md:grid-cols-2">
        {PROFILE_SCALAR_KEYS.map((key) => (
          <div key={key} className="border-b border-slate-50 pb-4">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {formatFieldLabel(String(key))}
            </dt>
            <dd className="mt-1 text-sm text-slate-900">{formatScalar(profile[key])}</dd>
          </div>
        ))}
        {PROFILE_LIST_KEYS.map((key) => (
          <div key={key} className="border-b border-slate-50 pb-4 md:col-span-2">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {formatFieldLabel(String(key))}
            </dt>
            <dd className="mt-2">
              <TagList items={(profile[key] as string[] | undefined) ?? []} />
            </dd>
          </div>
        ))}
        <div className="border-b border-slate-50 pb-4 md:col-span-2">
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Summary</dt>
          <dd className="mt-2">
            {profile.summary?.trim() ? (
              <ExpandableText text={profile.summary} />
            ) : (
              <span className="text-sm text-slate-400">{NULL_DISPLAY}</span>
            )}
          </dd>
        </div>
        {profile.extensions && Object.keys(profile.extensions).length > 0 ? (
          <div className="border-b border-slate-50 pb-4 md:col-span-2">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Extensions
            </dt>
            <dd className="mt-2">
              <ExpandableText text={JSON.stringify(profile.extensions, null, 2)} />
            </dd>
          </div>
        ) : null}
      </div>
    </section>
  )
}
