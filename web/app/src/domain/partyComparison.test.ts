import { describe, expect, it } from 'vitest'
import type { ResultRecord } from './schemas'
import {
  PARTY_COMPARISON_NO_VOTES_COLOR,
  PARTY_COMPARISON_TIE_COLOR,
  partyComparisonBalance,
  partyComparisonColor,
} from './partyComparison'

describe('two-party comparison calculations', () => {
  it('measures each party within their combined vote', () => {
    expect(partyComparisonBalance(record({ a: 60, b: 40 }), 'a', 'b')).toBe(0.6)
    expect(partyComparisonBalance(record({ a: 0, b: 0 }), 'a', 'b')).toBeNull()
  })

  it('uses both endpoints, a white tie, and a separate no-votes state', () => {
    expect(partyComparisonColor('#2244aa', '#cc3322', 1)).toBe('#2244aa')
    expect(partyComparisonColor('#2244aa', '#cc3322', 0)).toBe('#cc3322')
    expect(partyComparisonColor('#2244aa', '#cc3322', 0.5)).toBe(
      PARTY_COMPARISON_TIE_COLOR,
    )
    expect(partyComparisonColor('#2244aa', '#cc3322', null)).toBe(
      PARTY_COMPARISON_NO_VOTES_COLOR,
    )
  })
})

function record(partyVotes: Record<string, number>): ResultRecord {
  const validVotes = Object.values(partyVotes).reduce((sum, votes) => sum + votes, 0)
  return {
    id: 'loc:1',
    geographyType: 'locality',
    names: { en: 'Test', he: 'Test' },
    code: '1',
    localityId: 'loc:1',
    totals: {
      contributingRows: 1,
      contributingKalpis: 1,
      eligibleVoters: validVotes,
      actualVoters: validVotes,
      validVotes,
      invalidVotes: 0,
      turnout: 1,
    },
    winner: {
      partyId: 'a',
      votes: partyVotes.a ?? 0,
      runnerUpVotes: partyVotes.b ?? 0,
      marginVotes: (partyVotes.a ?? 0) - (partyVotes.b ?? 0),
      voteShare: validVotes > 0 ? (partyVotes.a ?? 0) / validVotes : 0,
    },
    partyVotes,
  }
}
