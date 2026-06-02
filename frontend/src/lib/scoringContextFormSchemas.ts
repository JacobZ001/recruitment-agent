export type Dimension = 'organization' | 'recruiter_actor' | 'job'

export type TagValidationError = {
  code: 'too_many' | 'too_long' | 'empty'
  message: string
}

export const TAG_MAX_COUNT = 8
export const TAG_MAX_LEN = 120

export function normalizeTag(raw: string): string {
  return raw.replace(/\s+/g, ' ').trim()
}

export function validateAddTag(existing: string[], nextRaw: string): TagValidationError | null {
  const next = normalizeTag(nextRaw)
  if (!next) return { code: 'empty', message: 'Tag Cannot Be Empty.' }
  if (next.length > TAG_MAX_LEN) {
    return { code: 'too_long', message: `Tag Must Be ≤ ${TAG_MAX_LEN} Characters.` }
  }
  const unique = new Set(existing.map(normalizeTag))
  unique.delete('')
  if (!unique.has(next) && unique.size >= TAG_MAX_COUNT) {
    return { code: 'too_many', message: `You Can Add Up To ${TAG_MAX_COUNT} Tags.` }
  }
  return null
}

export function addTag(existing: string[], nextRaw: string): { next: string[]; error: TagValidationError | null } {
  const err = validateAddTag(existing, nextRaw)
  if (err) return { next: existing, error: err }
  const next = normalizeTag(nextRaw)
  const unique = new Set(existing.map(normalizeTag))
  unique.delete('')
  unique.add(next)
  return { next: [...unique], error: null }
}

export function removeTag(existing: string[], tag: string): string[] {
  const t = normalizeTag(tag)
  return existing.map(normalizeTag).filter((x) => x && x !== t)
}

export type OrganizationFormValues = {
  company_name: string
  industry: string
  team_name: string
  environment_signals: string[]
  preference_signals: string[]
  summary: string
}

export type RecruiterActorFormValues = {
  actor_id: string
  actor_role: string
  preference_signals: string[]
  avoid_signals: string[]
}

export type JobFormValues = {
  role_title: string
  must_haves: string[]
  nice_to_have: string[]
  success: string[]
  responsibilities: string[]
}

export type FieldErrorMap<T extends string> = Partial<Record<T, string>>

export type OrganizationField =
  | 'company_name'
  | 'industry'
  | 'team_name'
  | 'environment_signals'
  | 'preference_signals'
  | 'summary'

export type RecruiterActorField = 'actor_id' | 'actor_role' | 'preference_signals' | 'avoid_signals'

export type JobField = 'role_title' | 'must_haves' | 'nice_to_have' | 'success' | 'responsibilities'

export function validateOrganizationForm(v: OrganizationFormValues): FieldErrorMap<OrganizationField> {
  const errors: FieldErrorMap<OrganizationField> = {}
  if (!v.company_name.trim()) errors.company_name = 'Company Name Is Required.'
  if (v.environment_signals.length < 1) errors.environment_signals = 'Add At Least One Tag.'
  if (v.preference_signals.length < 1) errors.preference_signals = 'Add At Least One Tag.'
  return errors
}

export function validateRecruiterActorForm(
  v: RecruiterActorFormValues,
): FieldErrorMap<RecruiterActorField> {
  const errors: FieldErrorMap<RecruiterActorField> = {}
  if (!v.actor_id.trim()) errors.actor_id = 'Your Name Or Recruiter ID Is Required.'
  const tagCount = v.preference_signals.length + v.avoid_signals.length
  if (tagCount < 1) errors.preference_signals = 'Add At Least One Tag In Look For Or Avoid.'
  return errors
}

export function validateJobForm(v: JobFormValues): FieldErrorMap<JobField> {
  const errors: FieldErrorMap<JobField> = {}
  if (!v.role_title.trim()) errors.role_title = 'Job Title Is Required.'
  const anySignals = v.must_haves.length > 0 || v.success.length > 0 || v.responsibilities.length > 0
  if (!anySignals) errors.must_haves = 'Add Tags To Must-Haves, Success, Or Responsibilities.'
  return errors
}

export function joinTagsAsNewlines(tags: string[]): string {
  return tags.map(normalizeTag).filter(Boolean).join('\n')
}

export function defaultOrganizationForm(): OrganizationFormValues {
  return {
    company_name: '',
    industry: '',
    team_name: '',
    environment_signals: [],
    preference_signals: [],
    summary: '',
  }
}

export function defaultRecruiterActorForm(): RecruiterActorFormValues {
  return {
    actor_id: '',
    actor_role: '',
    preference_signals: [],
    avoid_signals: [],
  }
}

export function defaultJobForm(): JobFormValues {
  return {
    role_title: '',
    must_haves: [],
    nice_to_have: [],
    success: [],
    responsibilities: [],
  }
}

function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((x) => typeof x === 'string')
}

export function parseOrganizationContext(o: unknown): OrganizationFormValues | null {
  if (!o || typeof o !== 'object') return null
  const obj = o as Record<string, unknown>
  const company_name = typeof obj.company_name === 'string' ? obj.company_name : ''
  if (!company_name.trim()) return null
  return {
    company_name,
    industry: typeof obj.industry === 'string' ? obj.industry : '',
    team_name: typeof obj.team_name === 'string' ? obj.team_name : '',
    environment_signals: isStringArray(obj.environment_signals) ? obj.environment_signals : [],
    preference_signals: isStringArray(obj.preference_signals) ? obj.preference_signals : [],
    summary: typeof obj.summary === 'string' ? obj.summary : '',
  }
}

export function parseRecruiterActorContext(o: unknown): RecruiterActorFormValues | null {
  if (!o || typeof o !== 'object') return null
  const obj = o as Record<string, unknown>
  const actor_id = typeof obj.actor_id === 'string' ? obj.actor_id : ''
  if (!actor_id.trim()) return null
  return {
    actor_id,
    actor_role: typeof obj.actor_role === 'string' ? obj.actor_role : '',
    preference_signals: isStringArray(obj.preference_signals) ? obj.preference_signals : [],
    avoid_signals: isStringArray(obj.avoid_signals) ? obj.avoid_signals : [],
  }
}

export function parseJobContext(o: unknown): JobFormValues | null {
  if (!o || typeof o !== 'object') return null
  const obj = o as Record<string, unknown>
  const title = typeof obj.title === 'string' ? obj.title : ''
  if (!title.trim()) return null
  return {
    role_title: title,
    must_haves: isStringArray(obj.hard_requirements) ? obj.hard_requirements : [],
    nice_to_have: isStringArray(obj.preferred_requirements) ? obj.preferred_requirements : [],
    success: isStringArray(obj.success_signals) ? obj.success_signals : [],
    responsibilities: isStringArray(obj.responsibilities) ? obj.responsibilities : [],
  }
}

