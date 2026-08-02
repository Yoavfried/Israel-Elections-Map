import type { Language, Party, ResultRecord } from './schemas'
import { clampUnit, mixHexColors, normalizeHexColor } from './color'

export const PARTY_MAP_ZERO_COLOR = '#ffffff'
export const PARTY_MAP_UPPER_PERCENTILE = 0.95

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
  const positiveShares = records
    .map((record) => partyVoteShare(record, partyId))
    .filter((share) => share > 0)
    .toSorted((left, right) => left - right)

  if (positiveShares.length === 0) {
    return 0
  }

  const position = (positiveShares.length - 1) * PARTY_MAP_UPPER_PERCENTILE
  const lowerIndex = Math.floor(position)
  const upperIndex = Math.ceil(position)
  const interpolation = position - lowerIndex
  return (
    positiveShares[lowerIndex] +
    (positiveShares[upperIndex] - positiveShares[lowerIndex]) * interpolation
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
