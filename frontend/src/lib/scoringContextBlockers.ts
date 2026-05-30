/** Deterministic backend blocker string → recruiter-readable copy (R-014.1). */

export const KNOWN_MATERIALIZATION_BLOCKERS = [
  'organization authoring prose is missing or not confirmed',
  'recruiter actor authoring prose is missing or not confirmed',
  'job authoring prose is missing or not confirmed',
  'organization_context must include non-empty company_name plus bounded environment_signals and preference_signals before ready',
  'recruiter_actor_context must include actor_id plus at least one recruiter preference or avoid signal before ready',
  'job_context must include title plus bounded role signals before ready',
  'materialized L2 criteria must be non-empty before ready',
  'materialized L3 criteria must be non-empty before ready',
] as const

const BLOCKER_FRIENDLY_COPY: Record<(typeof KNOWN_MATERIALIZATION_BLOCKERS)[number], string> = {
  'organization authoring prose is missing or not confirmed':
    'Open Scoring context and describe your organization, then confirm.',
  'recruiter actor authoring prose is missing or not confirmed':
    'Open Scoring context and describe your preferences, then confirm.',
  'job authoring prose is missing or not confirmed':
    'Open Scoring context and describe who you are hiring, then confirm.',
  'organization_context must include non-empty company_name plus bounded environment_signals and preference_signals before ready':
    'Organization needs a company name, work environment, and values — edit Organization with clearer detail and confirm again.',
  'recruiter_actor_context must include actor_id plus at least one recruiter preference or avoid signal before ready':
    'Preferences need your name plus what you value or avoid — edit Preferences and confirm again.',
  'job_context must include title plus bounded role signals before ready':
    'Role description needs a job title and requirements — edit Who You\'re Hiring and confirm again.',
  'materialized L2 criteria must be non-empty before ready':
    'Scoring criteria are not ready yet — confirm all three sections with enough detail.',
  'materialized L3 criteria must be non-empty before ready':
    'Detailed scoring criteria are not ready yet — confirm all three sections with enough detail.',
}

export function mapMaterializationBlocker(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return trimmed
  return BLOCKER_FRIENDLY_COPY[trimmed as keyof typeof BLOCKER_FRIENDLY_COPY] ?? trimmed
}

export function mapMaterializationBlockers(blockers: string[]): string[] {
  return blockers.map(mapMaterializationBlocker)
}

/** Blockers that indicate typed/materialized gaps (checklist item 4), not missing prose alone. */
const MATERIALIZED_BLOCKER_PREFIXES = [
  'organization_context must',
  'recruiter_actor_context must',
  'job_context must',
  'materialized L2',
  'materialized L3',
] as const

export function isMaterializedCriteriaBlocker(raw: string): boolean {
  const t = raw.trim()
  return MATERIALIZED_BLOCKER_PREFIXES.some((p) => t.startsWith(p))
}

export type ChecklistDimension = 'organization' | 'recruiter_actor' | 'job'

export function blockerTargetDimension(raw: string): ChecklistDimension | 'materialized' {
  const t = raw.trim()
  if (t.startsWith('organization')) return 'organization'
  if (t.startsWith('recruiter')) return 'recruiter_actor'
  if (t.startsWith('job')) return 'job'
  return 'materialized'
}
