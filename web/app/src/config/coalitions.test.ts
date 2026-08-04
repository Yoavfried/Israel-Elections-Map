import { describe, expect, it } from 'vitest'
import { COALITION_DEFINITIONS } from './coalitions'

describe('coalition definitions', () => {
  it('covers every supported election with unique member lists', () => {
    expect(Object.keys(COALITION_DEFINITIONS)).toEqual([
      'K17',
      'K18',
      'K19',
      'K20',
      'K21',
      'K22',
      'K23',
      'K24',
      'K25',
    ])

    for (const definition of Object.values(COALITION_DEFINITIONS)) {
      expect(definition.memberPartyIds.length).toBeGreaterThan(0)
      expect(new Set(definition.memberPartyIds).size).toBe(
        definition.memberPartyIds.length,
      )
      for (const partialPartyId of Object.keys(definition.partialMembership ?? {})) {
        expect(definition.memberPartyIds).toContain(partialPartyId)
      }
      expect(definition.sourceUrls.length).toBeGreaterThan(0)
    }
  })

  it('uses the outgoing transitional coalition for both 2019 Knessets', () => {
    expect(COALITION_DEFINITIONS.K21.kind).toBe('transitional')
    expect(COALITION_DEFINITIONS.K22.kind).toBe('transitional')
    expect(COALITION_DEFINITIONS.K23.kind).toBe('first')
    expect(Object.keys(COALITION_DEFINITIONS.K21.partialMembership ?? {})).toEqual(['טב'])
    expect(Object.keys(COALITION_DEFINITIONS.K22.partialMembership ?? {})).toEqual(['טב'])
    expect(Object.keys(COALITION_DEFINITIONS.K23.partialMembership ?? {})).toEqual([
      'פה',
      'אמת',
    ])
    expect(COALITION_DEFINITIONS.K23.memberPartyIds).not.toContain('טב')
  })
})
