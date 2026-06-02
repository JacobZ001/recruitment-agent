import { describe, expect, it } from 'vitest'
import {
  TAG_MAX_COUNT,
  TAG_MAX_LEN,
  addTag,
  defaultJobForm,
  defaultOrganizationForm,
  defaultRecruiterActorForm,
  joinTagsAsNewlines,
  parseJobContext,
  parseOrganizationContext,
  parseRecruiterActorContext,
  validateJobForm,
  validateOrganizationForm,
  validateRecruiterActorForm,
} from './scoringContextFormSchemas'

describe('tag helpers', () => {
  it('enforces max count and max length', () => {
    let tags: string[] = []
    for (let i = 0; i < TAG_MAX_COUNT; i += 1) {
      const res = addTag(tags, `t${i}`)
      expect(res.error).toBeNull()
      tags = res.next
    }
    const over = addTag(tags, 'extra')
    expect(over.error?.message).toContain(String(TAG_MAX_COUNT))

    const long = addTag([], 'x'.repeat(TAG_MAX_LEN + 1))
    expect(long.error?.message).toContain(String(TAG_MAX_LEN))
  })

  it('joins tags as newline strings deterministically', () => {
    expect(joinTagsAsNewlines([' a ', '', 'b'])).toBe('a\nb')
  })
})

describe('form validation', () => {
  it('validates organization required fields', () => {
    const v = defaultOrganizationForm()
    const err = validateOrganizationForm(v)
    expect(err.company_name).toBeTruthy()
    expect(err.environment_signals).toBeTruthy()
    expect(err.preference_signals).toBeTruthy()
  })

  it('validates recruiter actor needs actor_id and at least one tag', () => {
    const v = defaultRecruiterActorForm()
    let err = validateRecruiterActorForm(v)
    expect(err.actor_id).toBeTruthy()
    expect(err.preference_signals).toBeTruthy()
    v.actor_id = 'Jane'
    err = validateRecruiterActorForm(v)
    expect(err.preference_signals).toBeTruthy()
  })

  it('validates job requires title + at least one signal group', () => {
    const v = defaultJobForm()
    let err = validateJobForm(v)
    expect(err.role_title).toBeTruthy()
    v.role_title = 'Ops'
    err = validateJobForm(v)
    expect(err.must_haves).toBeTruthy()
  })
})

describe('typed context parsers', () => {
  it('parses org typed context', () => {
    expect(parseOrganizationContext(null)).toBeNull()
    expect(parseOrganizationContext({})).toBeNull()
    const parsed = parseOrganizationContext({
      company_name: 'BlueOcean',
      environment_signals: ['a'],
      preference_signals: ['b'],
    })
    expect(parsed?.company_name).toBe('BlueOcean')
  })

  it('parses recruiter actor typed context', () => {
    expect(parseRecruiterActorContext({})).toBeNull()
    const parsed = parseRecruiterActorContext({
      actor_id: 'Jane',
      preference_signals: ['Ownership'],
      avoid_signals: [],
    })
    expect(parsed?.actor_id).toBe('Jane')
  })

  it('parses job typed context', () => {
    expect(parseJobContext({})).toBeNull()
    const parsed = parseJobContext({
      title: 'Recruiter',
      hard_requirements: ['a'],
      preferred_requirements: [],
      success_signals: ['b'],
      responsibilities: ['c'],
    })
    expect(parsed?.role_title).toBe('Recruiter')
    expect(parsed?.must_haves.length).toBe(1)
  })
})

