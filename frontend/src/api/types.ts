export type CandidateViewStatus = {
  kind: string
}

export type RecruiterActionItem = {
  key: string
  label: string
  event_type: string
  group: string
  order: number
}

export type CandidateListItemOverallScore = {
  value: number | null
  type: string | null
}

export type CandidateGovernanceFlags = {
  orphan_ingress: boolean
  dedup_status?: string | null
  dedup_pending_resolution: boolean
  dedup_linked_to_candidate_id?: string | null
  dedup_match_count?: number | null
}

export type DedupMatch = {
  candidate_id: string
  match_kinds: string[]
  full_name?: string | null
}

export type CandidateListItem = {
  candidate_id: string
  full_name: string
  stage: string
  status: CandidateViewStatus
  headline: string
  summary: string
  top_skills: string[]
  overall_score?: CandidateListItemOverallScore | null
  rank?: number | null
  total_candidates?: number | null
  available_actions: RecruiterActionItem[]
  governance_flags?: CandidateGovernanceFlags
}

export type ScoringContextSummary = {
  context_version: number
  status: string
  organization?: string | null
  recruiter_actor_id?: string | null
  job_title?: string | null
} | null

export type ScoringContextResponse = {
  context_version: number
  status: string
  organization_authoring_text: string
  recruiter_actor_authoring_text: string
  job_authoring_text: string
  organization_context?: Record<string, unknown> | null
  recruiter_actor_context?: Record<string, unknown> | null
  job_context?: Record<string, unknown> | null
  derived_l2_criteria: string[]
  derived_l3_criteria: string[]
  created_at: string
  updated_at: string
  ready_at?: string | null
  stale_at?: string | null
  source_refs: string[]
}

export type CandidateCreatePdfIngressResponse = {
  candidate_id: string
  ingress_accepted: boolean
  publish_status: string
  event_id: string
  event_type: string
  publish_result: Record<string, unknown>
  state_summary?: {
    pipeline_phase: string
    transitions_count: number
    state_id: string
    store_revision?: number | null
  } | null
}

export type ScoreCriterion = {
  name: string
  score: number | null
  confidence: number | null
  source: string
  reason?: string | null
}

export type CandidateProfile = {
  full_name?: string | null
  primary_email?: string | null
  primary_phone?: string | null
  preferred_contact_method?: string | null
  location?: string | null
  timezone?: string | null
  external_profile_urls?: string[]
  headline?: string | null
  summary: string
  seniority?: string | null
  years_experience?: number | null
  languages?: string[]
  skills: string[]
  industries?: string[]
  roles?: string[]
  work_authorization?: string | null
  compensation_expectation?: string | null
  availability_date?: string | null
  extensions: Record<string, unknown>
} | null

export type CandidateScores = {
  criteria?: ScoreCriterion[]
  overall_score?: CandidateListItemOverallScore | null
  context_version?: number | null
  stale?: boolean | null
}

export type CandidateViewResponse = {
  candidate_id: string
  stage: string
  status: CandidateViewStatus
  summary: string
  profile?: CandidateProfile
  decision: Record<string, unknown>
  evaluation?: Record<string, unknown> | null
  scoring_context?: Record<string, unknown> | null
  flags: Record<string, unknown>
  scores: CandidateScores
  ranking: Record<string, unknown>
  available_actions: RecruiterActionItem[]
  next_actions: string[]
  governance_flags?: CandidateGovernanceFlags
}

export type ApiErrorBody = {
  code?: string
  message?: string
}
