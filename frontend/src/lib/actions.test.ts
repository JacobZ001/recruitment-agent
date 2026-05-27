import { describe, expect, it } from 'vitest'
import { actionsByGroup } from '@/lib/actions'

describe('actionsByGroup', () => {
  it('sorts by order then label then event_type and preserves group order', () => {
    const actions = [
      { group: 'b', order: 2, label: 'B', event_type: 'recruiter_b' },
      { group: 'a', order: 1, label: 'Z', event_type: 'recruiter_z' },
      { group: 'a', order: 1, label: 'A', event_type: 'recruiter_a' },
    ]
    const g = actionsByGroup(actions)
    expect(g.map((x) => x.group)).toEqual(['a', 'b'])
    expect(g[0].actions.map((a) => a.event_type)).toEqual(['recruiter_a', 'recruiter_z'])
    expect(g[1].actions[0].event_type).toBe('recruiter_b')
  })
})
