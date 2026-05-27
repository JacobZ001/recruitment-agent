import { describe, expect, it } from 'vitest'
import { extractApiError } from '@/api/client'

describe('extractApiError', () => {
  it('parses FastAPI detail object with code and message', () => {
    expect(
      extractApiError({
        detail: { code: 'invalid_candidate_action', message: 'not allowed' },
      }),
    ).toEqual({ code: 'invalid_candidate_action', message: 'not allowed' })
  })

  it('parses string detail', () => {
    expect(extractApiError({ detail: 'missing candidate' })).toEqual({
      message: 'missing candidate',
    })
  })

  it('returns null for empty body', () => {
    expect(extractApiError(null)).toBeNull()
  })
})
