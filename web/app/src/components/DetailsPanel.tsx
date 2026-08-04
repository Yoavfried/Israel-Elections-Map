import { useMemo } from 'react'
import { Info } from 'lucide-react'
import { formatNumber, formatPercent } from '../domain/format'
import type {
  GeographySearchItem,
  Language,
  Party,
  ResultRecord,
} from '../domain/schemas'
import { translate } from '../i18n/translations'

interface DetailsPanelProps {
  language: Language
  record: ResultRecord | null
  emptySelection?: GeographySearchItem | null
  parties: Party[]
  highlightedPartyIds?: string[]
  highlightedPartiesLabel?: string
  highlightedPartyTotalLabel?: string
  highlightedPartyNotes?: Readonly<Record<string, string>>
}

export function DetailsPanel({
  language,
  record,
  emptySelection = null,
  parties,
  highlightedPartyIds = [],
  highlightedPartiesLabel,
  highlightedPartyTotalLabel,
  highlightedPartyNotes = {},
}: DetailsPanelProps) {
  const partyById = useMemo(() => new Map(parties.map((party) => [party.id, party])), [parties])
  const highlightedPartyIdSet = useMemo(
    () => new Set(highlightedPartyIds),
    [highlightedPartyIds],
  )

  if (!record && emptySelection) {
    const notice = emptySelection.notice?.[language]
    return (
      <aside className="details-panel details-panel--empty details-panel--no-result">
        <span className="selection-marker" aria-hidden="true" />
        <div>
          <h2 dir="auto">{emptySelection.names[language]}</h2>
          <p>{translate(language, 'noMappedResult')}</p>
          {notice ? (
            <div className="details-notice" role="note">
              <Info size={17} strokeWidth={2} aria-hidden="true" />
              <span dir="auto">{notice}</span>
            </div>
          ) : null}
        </div>
      </aside>
    )
  }

  if (!record) {
    return (
      <aside className="details-panel details-panel--empty">
        <span className="selection-marker" aria-hidden="true" />
        <div>
          <h2>{translate(language, 'selectionPromptTitle')}</h2>
          <p>{translate(language, 'selectionPromptBody')}</p>
        </div>
      </aside>
    )
  }

  const winner = partyById.get(record.winner.partyId)
  const isEnvelope = record.geographyType === 'envelope'
  const partyName = (partyId: string) => partyById.get(partyId)?.names[language] ?? partyId
  const collator = new Intl.Collator(language === 'he' ? 'he-IL' : 'en-IL')
  const orderedParties = Object.entries(record.partyVotes)
    .toSorted(
      (left, right) =>
        right[1] - left[1] || collator.compare(partyName(left[0]), partyName(right[0])),
    )
  const largestPartyVote = Math.max(orderedParties[0]?.[1] ?? 0, 1)
  const includedNames = record.includedNames?.[language] ?? []
  const includedLabel = `${translate(language, 'includesLocalities')}: ${includedNames.join(', ')}`
  const notice = record.notice?.[language]
  const highlightedParties = highlightedPartyIds.map((partyId) => ({
    partyId,
    party: partyById.get(partyId) ?? null,
    votes: record.partyVotes[partyId] ?? 0,
  }))
  const highlightedPartyVotes = highlightedParties.reduce(
    (total, highlightedParty) => total + highlightedParty.votes,
    0,
  )
  const highlightedLabel =
    highlightedPartiesLabel ?? translate(language, 'partyComparisonDetails')

  return (
    <aside className="details-panel">
      <div className="details-heading">
        <div className="details-title-row">
          <h2 dir={isEnvelope ? undefined : 'auto'}>
            {isEnvelope ? translate(language, 'envelopeVotes') : record.names[language]}
          </h2>
          {includedNames.length > 0 ? (
            <span
              className="included-localities-info"
              tabIndex={0}
              aria-label={includedLabel}
            >
              <Info size={16} strokeWidth={2} aria-hidden="true" />
              <span className="included-localities-tooltip" role="tooltip">
                {includedLabel}
              </span>
            </span>
          ) : null}
        </div>
        <span
          className="party-swatch party-swatch--large"
          style={{ backgroundColor: winner?.color ?? '#68706a' }}
          aria-hidden="true"
        />
      </div>

      {notice ? (
        <div className="details-notice" role="note">
          <Info size={17} strokeWidth={2} aria-hidden="true" />
          <span dir="auto">{notice}</span>
        </div>
      ) : null}

      <div className="winner-card">
        <span>{translate(language, 'winner')}</span>
        <strong dir="auto">{winner?.names[language] ?? record.winner.partyId}</strong>
        <span>{formatPercent(record.winner.voteShare, language)}</span>
      </div>

      {highlightedParties.length > 0 ? (
        <div
          className="party-highlight-summary"
          aria-label={highlightedLabel}
        >
          {highlightedPartyTotalLabel ? (
            <div className="party-highlight-summary__heading">
              <span>{highlightedPartyTotalLabel}</span>
              <strong>
                {formatNumber(highlightedPartyVotes, language)} ·{' '}
                {formatPercent(
                  record.totals.validVotes > 0
                    ? highlightedPartyVotes / record.totals.validVotes
                    : 0,
                  language,
                )}
              </strong>
            </div>
          ) : null}
          <div className="party-highlight-details">
            {highlightedParties.map(({ partyId, party, votes }) => (
              <div key={partyId}>
                <span
                  className="party-swatch"
                  style={{ backgroundColor: party?.color ?? '#68706a' }}
                  aria-hidden="true"
                />
                <span className="party-highlight-name">
                  <span dir="auto" title={party?.names[language] ?? partyId}>
                    {party?.names[language] ?? partyId}
                  </span>
                  {highlightedPartyNotes[partyId] ? (
                    <span
                      className="party-highlight-note"
                      tabIndex={0}
                      aria-label={highlightedPartyNotes[partyId]}
                    >
                      <Info size={14} strokeWidth={2} aria-hidden="true" />
                      <span role="tooltip" dir="auto">
                        {highlightedPartyNotes[partyId]}
                      </span>
                    </span>
                  ) : null}
                </span>
                <strong>{formatNumber(votes, language)}</strong>
                <span>
                  {formatPercent(
                    record.totals.validVotes > 0 ? votes / record.totals.validVotes : 0,
                    language,
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <dl className={`metric-grid${isEnvelope ? ' metric-grid--envelope' : ''}`}>
        {!isEnvelope ? (
          <div>
            <dt>{translate(language, 'turnout')}</dt>
            <dd>
              {record.totals.turnout === null
                ? translate(language, 'notAvailable')
                : formatPercent(record.totals.turnout, language)}
            </dd>
          </div>
        ) : null}
        <div>
          <dt>{translate(language, 'actualVoters')}</dt>
          <dd>{formatNumber(record.totals.actualVoters, language)}</dd>
        </div>
        <div>
          <dt>{translate(language, 'validVotes')}</dt>
          <dd>{formatNumber(record.totals.validVotes, language)}</dd>
        </div>
      </dl>

      <div className="party-breakdown">
        <div className="section-heading">
          <h3>{translate(language, 'ballotBreakdown')}</h3>
          <span>
            {formatNumber(record.totals.contributingKalpis, language)}{' '}
            {translate(language, 'contributingKalpis')}
          </span>
        </div>
        <ol>
          {orderedParties.map(([partyId, votes]) => {
            const party = partyById.get(partyId)
            return (
              <li
                key={partyId}
                className={
                  highlightedPartyIdSet.has(partyId)
                    ? 'party-breakdown__highlighted'
                    : undefined
                }
              >
                <span
                  className="party-swatch"
                  style={{ backgroundColor: party?.color ?? '#68706a' }}
                  aria-hidden="true"
                />
                <span
                  className="party-name"
                  dir="auto"
                  title={party?.names[language] ?? partyId}
                >
                  {party?.names[language] ?? partyId}
                </span>
                <span className="party-votes">{formatNumber(votes, language)}</span>
                <span className="party-bar" aria-hidden="true">
                  <span
                    style={{
                      inlineSize: `${(votes / largestPartyVote) * 100}%`,
                      backgroundColor: party?.color ?? '#68706a',
                    }}
                  />
                </span>
                <span className="party-share">
                  {formatPercent(
                    record.totals.validVotes > 0 ? votes / record.totals.validVotes : 0,
                    language,
                  )}
                </span>
              </li>
            )
          })}
        </ol>
      </div>
    </aside>
  )
}
