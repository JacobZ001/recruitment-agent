import type {
  ApiErrorBody,
  CandidateListItem,
  CandidateViewResponse,
  ScoringContextResponse,
} from '@/api/types'

export class ApiRequestError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.body = body
  }
}

export function extractApiError(body: unknown): ApiErrorBody | null {
  if (body === null || body === undefined) return null
  if (typeof body === 'string') return { message: body }
  if (typeof body !== 'object') return null
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') return { message: detail }
  if (detail && typeof detail === 'object') {
    const o = detail as Record<string, unknown>
    return {
      code: typeof o.code === 'string' ? o.code : undefined,
      message: typeof o.message === 'string' ? o.message : undefined,
    }
  }
  return null
}

async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    return { message: text }
  }
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  const body = await parseJsonSafe(res)
  if (!res.ok) {
    const parsed = extractApiError(body)
    const msg = parsed?.message ?? parsed?.code ?? res.statusText
    throw new ApiRequestError(msg || `HTTP ${res.status}`, res.status, body)
  }
  return body as T
}

export function listCandidates(): Promise<CandidateListItem[]> {
  return fetchJson<CandidateListItem[]>('/candidates')
}

export function getScoringContext(): Promise<ScoringContextResponse> {
  return fetchJson<ScoringContextResponse>('/scoring-context')
}

export function getCandidate(candidateId: string): Promise<CandidateViewResponse> {
  return fetchJson<CandidateViewResponse>(`/candidate/${candidateId}`)
}

export function postCandidateAction(
  candidateId: string,
  eventType: string,
  payload: Record<string, unknown>,
): Promise<CandidateViewResponse> {
  return fetchJson<CandidateViewResponse>(`/candidates/${candidateId}/action`, {
    method: 'POST',
    body: JSON.stringify({ event_type: eventType, payload }),
  })
}
