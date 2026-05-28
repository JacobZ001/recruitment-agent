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

export type CandidateListItem = {
  candidate_id: string
  stage: string
  status: CandidateViewStatus
  headline: string
  summary: string
  top_skills: string[]
  overall_score?: CandidateListItemOverallScore | null
  rank?: number | null
  total_candidates?: number | null
  available_actions: RecruiterActionItem[]
}

export type ScoringContextSummary = {
  context_version: number
  status: string
  organization?: string | null
  recruiter_actor_id?: string | null
  job_title?: string | null
} | null

export type ScoreCriterion = {
  name: string
  score: number | null
  confidence: number | null
  source: string
  reason?: string | null
}

export type CandidateProfile = {
  years_experience?: number | null
  seniority?: 'junior' | 'mid' | 'senior' | string | null
  roles: string[]
  skills: string[]
  industries: string[]
  summary: string
  extensions: Record<string, unknown>
} | null

export type CandidateViewResponse = {
  candidate_id: string
  stage: string
  status: CandidateViewStatus
  summary: string
  profile?: CandidateProfile
  decision: Record<string, unknown>
  evaluation?: Record<string, unknown> | null
  scoring_context?: ScoringContextSummary
  flags: Record<string, unknown>
  scores: {
    criteria?: ScoreCriterion[]
    overall_score?: { value?: number | null; type?: string | null }
  }
  ranking: Record<string, unknown>
  available_actions: RecruiterActionItem[]
  next_actions: string[]
}

export type ApiErrorBody = {
  code?: string
  message?: string
}
