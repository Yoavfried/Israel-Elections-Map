import type { Language, Party, ResultRecord } from './schemas'
import { clampUnit, mixHexColors, normalizeHexColor } from './color'

export const PARTY_MAP_ZERO_COLOR = '#ffffff'
export const PARTY_MAP_UPPER_PERCENTILE = 0.95
export const PARTY_MAP_CIRCLE_UPPER_PERCENTILE = 0.99
export const PARTY_MAP_MAX_CIRCLE_RADIUS = 18
export const PARTY_MAP_MIN_CIRCLE_RADIUS = 2.5
const PARTY_MAP_CIRCLE_MIN_COLOR_INTENSITY = 0.22

export type PartyMapDisplayMode = 'areas' | 'circles'

export function partyVoteShare(record: ResultRecord, partyId: string): number {
  if (record.totals.validVotes <= 0) {
    return 0
  }
  return (record.partyVotes[partyId] ?? 0) / record.totals.validVotes
}

export function partyVoteShareUpperBound(
  records: ResultRecord[],
  partyId: string,
): number {
  return voteShareUpperBound(records, (record) => partyVoteShare(record, partyId))
}

export function partyVoteCount(record: ResultRecord, partyId: string): number {
  return record.partyVotes[partyId] ?? 0
}

export function partyVoteCountUpperBound(
  records: ResultRecord[],
): number {
  return positiveValueUpperBound(
    records.map((record) => Math.max(0, ...Object.values(record.partyVotes))),
    PARTY_MAP_CIRCLE_UPPER_PERCENTILE,
  )
}

export function voteShareUpperBound(
  records: ResultRecord[],
  shareForRecord: (record: ResultRecord) => number,
): number {
  return positiveValueUpperBound(records.map(shareForRecord), PARTY_MAP_UPPER_PERCENTILE)
}

export function partyVoteCircleRadius(votes: number, upperBoundVotes: number): number {
  if (votes <= 0 || upperBoundVotes <= 0) {
    return 0
  }
  const proportionalRadius =
    PARTY_MAP_MAX_CIRCLE_RADIUS * Math.sqrt(clampUnit(votes / upperBoundVotes))
  return Math.max(PARTY_MAP_MIN_CIRCLE_RADIUS, proportionalRadius)
}

function positiveValueUpperBound(values: number[], percentile: number): number {
  const positiveValues = values
    .filter((value) => value > 0)
    .toSorted((left, right) => left - right)

  if (positiveValues.length === 0) {
    return 0
  }

  const position = (positiveValues.length - 1) * percentile
  const lowerIndex = Math.floor(position)
  const upperIndex = Math.ceil(position)
  const interpolation = position - lowerIndex
  return (
    positiveValues[lowerIndex] +
    (positiveValues[upperIndex] - positiveValues[lowerIndex]) * interpolation
  )
}

export function rankPartiesForMap(
  parties: Party[],
  records: ResultRecord[],
  envelope: ResultRecord | null,
  language: Language,
): Party[] {
  const totals = new Map(parties.map((party) => [party.id, 0]))
  for (const record of [...records, ...(envelope ? [envelope] : [])]) {
    for (const party of parties) {
      totals.set(party.id, (totals.get(party.id) ?? 0) + (record.partyVotes[party.id] ?? 0))
    }
  }
  const collator = new Intl.Collator(language === 'he' ? 'he-IL' : 'en-IL')
  return parties.toSorted(
    (left, right) =>
      (totals.get(right.id) ?? 0) - (totals.get(left.id) ?? 0) ||
      collator.compare(left.names[language], right.names[language]) ||
      left.id.localeCompare(right.id),
  )
}

export function partyGradientColor(
  baseColor: string,
  share: number,
  upperBoundShare: number,
): string {
  const ratio = upperBoundShare > 0 ? clampUnit(share / upperBoundShare) : 0
  return mixHexColors(PARTY_MAP_ZERO_COLOR, normalizeHexColor(baseColor), ratio ** 2)
}

export function partyCircleColor(
  baseColor: string,
  share: number,
  upperBoundShare: number,
): string {
  if (share <= 0) {
    return PARTY_MAP_ZERO_COLOR
  }
  const ratio = upperBoundShare > 0 ? clampUnit(share / upperBoundShare) : 0
  const intensity =
    PARTY_MAP_CIRCLE_MIN_COLOR_INTENSITY +
    (1 - PARTY_MAP_CIRCLE_MIN_COLOR_INTENSITY) * ratio ** 1.5
  return mixHexColors(PARTY_MAP_ZERO_COLOR, normalizeHexColor(baseColor), intensity)
}
