import { describe, expect, it } from 'vitest'
import type { Party, ResultRecord } from './schemas'
import {
  PARTY_MAP_ZERO_COLOR,
  partyGradientColor,
  partyVoteShare,
  partyVoteShareUpperBound,
  rankPartiesForMap,
} from './partyMap'

const parties: Party[] = [
  party('a', 'Alpha', '#2244aa'),
  party('b', 'Beta', '#cc3322'),
]

describe('single-party map calculations', () => {
  it('computes vote shares and the positive-share 95th percentile', () => {
    const records = [
      record('one', 100, { a: 10, b: 90 }),
      record('two', 100, { a: 20, b: 80 }),
      record('three', 100, { a: 30, b: 70 }),
      record('four', 100, { a: 40, b: 60 }),
      record('outlier', 100, { a: 90, b: 10 }),
      record('zero', 100, { a: 0, b: 100 }),
    ]

    expect(partyVoteShare(records[0], 'a')).toBe(0.1)
    expect(partyVoteShareUpperBound(records, 'a')).toBeCloseTo(0.8)
  })

  it('maps zero to neutral and caps shares above the upper bound at full color', () => {
    expect(partyGradientColor('#2244aa', 0, 0.5)).toBe(PARTY_MAP_ZERO_COLOR)
    expect(partyGradientColor('#2244aa', 0.5, 0.5)).toBe('#2244aa')
    expect(partyGradientColor('#2244aa', 0.9, 0.5)).toBe('#2244aa')
    expect(partyGradientColor('#000000', 0.1, 1)).toBe('#fcfcfc')
  })

  it('orders the selector by mapped and envelope votes', () => {
    const records = [record('one', 100, { a: 40, b: 60 })]
    const envelope = record('envelope:official', 30, { a: 25, b: 5 })

    expect(rankPartiesForMap(parties, records, envelope, 'en').map((party) => party.id)).toEqual([
      'a',
      'b',
    ])
  })
})

function party(id: string, name: string, color: string): Party {
  return {
    id,
    ballotLetter: id,
    names: { en: name, he: name },
    listNameHe: name,
    wikipedia: { en: null, he: null },
    color,
    colorStatus: 'reviewed',
  }
}

function record(id: string, validVotes: number, partyVotes: Record<string, number>): ResultRecord {
  return {
    id,
    geographyType: id.startsWith('envelope:') ? 'envelope' : 'locality',
    names: { en: id, he: id },
    code: id,
    localityId: id.startsWith('envelope:') ? null : id,
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
      partyId: Object.keys(partyVotes)[0],
      votes: Object.values(partyVotes)[0],
      runnerUpVotes: 0,
      marginVotes: 0,
      voteShare: Object.values(partyVotes)[0] / validVotes,
    },
    partyVotes,
  }
}
