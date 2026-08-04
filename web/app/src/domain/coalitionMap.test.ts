import { describe, expect, it } from 'vitest'
import type { ResultRecord } from './schemas'
import { coalitionVoteShare, coalitionVoteShareUpperBound } from './coalitionMap'

describe('coalition map calculations', () => {
  it('sums each configured party once before calculating coalition share', () => {
    const result = record('one', 100, { a: 35, b: 20, c: 45 })

    expect(coalitionVoteShare(result, ['a', 'b'])).toBe(0.55)
    expect(coalitionVoteShare(result, ['a', 'a', 'b'])).toBe(0.55)
  })

  it('uses the positive-share 95th percentile for the color ceiling', () => {
    const records = [10, 20, 30, 40, 90].map((share, index) =>
      record(String(index), 100, { coalition: share, opposition: 100 - share }),
    )

    expect(coalitionVoteShareUpperBound(records, ['coalition'])).toBeCloseTo(0.8)
  })
})

function record(
  id: string,
  validVotes: number,
  partyVotes: Record<string, number>,
): ResultRecord {
  const [winnerPartyId, winnerVotes] = Object.entries(partyVotes).toSorted(
    (left, right) => right[1] - left[1],
  )[0]
  return {
    id,
    geographyType: 'locality',
    names: { en: id, he: id },
    code: id,
    localityId: id,
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
      partyId: winnerPartyId,
      votes: winnerVotes,
      runnerUpVotes: 0,
      marginVotes: 0,
      voteShare: winnerVotes / validVotes,
    },
    partyVotes,
  }
}
