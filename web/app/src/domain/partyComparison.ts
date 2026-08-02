import { mixHexColors, normalizeHexColor } from './color'
import type { ResultRecord } from './schemas'

export const PARTY_COMPARISON_TIE_COLOR = '#ffffff'
export const PARTY_COMPARISON_NO_VOTES_COLOR = '#e4e7e3'

export function partyComparisonBalance(
  record: ResultRecord,
  firstPartyId: string,
  secondPartyId: string,
): number | null {
  if (firstPartyId === secondPartyId) {
    return null
  }
  const firstVotes = record.partyVotes[firstPartyId] ?? 0
  const secondVotes = record.partyVotes[secondPartyId] ?? 0
  const combinedVotes = firstVotes + secondVotes
  return combinedVotes > 0 ? firstVotes / combinedVotes : null
}

export function partyComparisonColor(
  firstColor: string,
  secondColor: string,
  balance: number | null,
): string {
  if (balance === null) {
    return PARTY_COMPARISON_NO_VOTES_COLOR
  }
  if (balance >= 0.5) {
    return mixHexColors(
      PARTY_COMPARISON_TIE_COLOR,
      normalizeHexColor(firstColor),
      (balance - 0.5) * 2,
    )
  }
  return mixHexColors(
    normalizeHexColor(secondColor),
    PARTY_COMPARISON_TIE_COLOR,
    balance * 2,
  )
}
