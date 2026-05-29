import { describe, expect, it } from 'vitest'
import { formatFieldLabel, formatScorePercent } from '@/lib/format'

describe('formatFieldLabel', () => {
  it('capitalizes underscore keys and preserves Summary', () => {
    expect(formatFieldLabel('years_experience')).toBe('Years Experience')
    expect(formatFieldLabel('summary')).toBe('Summary')
  })
})

describe('formatScorePercent', () => {
  it('maps decimals to percent without extra rounding', () => {
    expect(formatScorePercent(0.82)).toBe('82%')
    expect(formatScorePercent(0.51375)).toBe('51.375%')
  })

  it('shows null placeholder', () => {
    expect(formatScorePercent(null)).toBe('— —')
  })
})
