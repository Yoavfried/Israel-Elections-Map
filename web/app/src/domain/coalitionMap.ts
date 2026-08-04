import type { ResultRecord } from './schemas'
import { voteShareUpperBound } from './partyMap'

export function coalitionVoteShare(
  record: ResultRecord,
  memberPartyIds: readonly string[],
): number {
  if (record.totals.validVotes <= 0) {
    return 0
  }
  const uniqueMemberIds = new Set(memberPartyIds)
  const coalitionVotes = [...uniqueMemberIds].reduce(
    (total, partyId) => total + (record.partyVotes[partyId] ?? 0),
    0,
  )
  return coalitionVotes / record.totals.validVotes
}

export function coalitionVoteShareUpperBound(
  records: ResultRecord[],
  memberPartyIds: readonly string[],
): number {
  return voteShareUpperBound(records, (record) =>
    coalitionVoteShare(record, memberPartyIds),
  )
}
