import { ChevronDown } from 'lucide-react'
import { formatNumber, formatPercent } from '../domain/format'
import type { Language, Party, ResultRecord } from '../domain/schemas'
import { translate } from '../i18n/translations'

interface EnvelopeSummaryProps {
  language: Language
  record: ResultRecord | null
  parties: Party[]
  selected: boolean
  onSelect: () => void
}

export function EnvelopeSummary({
  language,
  record,
  parties,
  selected,
  onSelect,
}: EnvelopeSummaryProps) {
  if (!record) {
    return null
  }

  const winner = parties.find((party) => party.id === record.winner.partyId)

  return (
    <button
      className={`envelope-summary${selected ? ' envelope-summary--selected' : ''}`}
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="envelope-summary__heading">
        <strong>{translate(language, 'envelopeVotes')}</strong>
        <ChevronDown
          className="envelope-summary__chevron"
          size={18}
          strokeWidth={2.2}
          aria-hidden="true"
        />
      </span>
      <span className="envelope-summary__result">
        <strong>{formatNumber(record.totals.actualVoters, language)}</strong>
        <span>
          {winner?.names[language] ?? record.winner.partyId} /{' '}
          {formatPercent(record.winner.voteShare, language)}
        </span>
      </span>
    </button>
  )
}
