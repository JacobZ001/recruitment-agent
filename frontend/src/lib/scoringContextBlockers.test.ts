import { describe, expect, it } from 'vitest'
import {
  KNOWN_MATERIALIZATION_BLOCKERS,
  blockerTargetDimension,
  mapMaterializationBlocker,
  mapMaterializationBlockers,
} from './scoringContextBlockers'

describe('mapMaterializationBlocker', () => {
  it.each(KNOWN_MATERIALIZATION_BLOCKERS)('maps known blocker: %s', (raw) => {
    const mapped = mapMaterializationBlocker(raw)
    expect(mapped).not.toBe('')
    expect(mapped).not.toBe(raw)
  })

  it('falls back to raw backend string for unknown blockers', () => {
    const unknown = 'unexpected validation failure from backend'
    expect(mapMaterializationBlocker(unknown)).toBe(unknown)
  })

  it('maps arrays deterministically', () => {
    const input = [
      KNOWN_MATERIALIZATION_BLOCKERS[0],
      'custom blocker xyz',
    ]
    expect(mapMaterializationBlockers(input)).toEqual([
      mapMaterializationBlocker(KNOWN_MATERIALIZATION_BLOCKERS[0]),
      'custom blocker xyz',
    ])
  })
})

describe('blockerTargetDimension', () => {
  it('routes organization blockers', () => {
    expect(blockerTargetDimension(KNOWN_MATERIALIZATION_BLOCKERS[0])).toBe('organization')
    expect(blockerTargetDimension(KNOWN_MATERIALIZATION_BLOCKERS[3])).toBe('organization')
  })

  it('routes recruiter blockers', () => {
    expect(blockerTargetDimension(KNOWN_MATERIALIZATION_BLOCKERS[1])).toBe('recruiter_actor')
    expect(blockerTargetDimension(KNOWN_MATERIALIZATION_BLOCKERS[4])).toBe('recruiter_actor')
  })

  it('routes job blockers', () => {
    expect(blockerTargetDimension(KNOWN_MATERIALIZATION_BLOCKERS[2])).toBe('job')
    expect(blockerTargetDimension(KNOWN_MATERIALIZATION_BLOCKERS[5])).toBe('job')
  })

  it('routes L2/L3 to materialized', () => {
    expect(blockerTargetDimension(KNOWN_MATERIALIZATION_BLOCKERS[6])).toBe('materialized')
    expect(blockerTargetDimension(KNOWN_MATERIALIZATION_BLOCKERS[7])).toBe('materialized')
  })
})
