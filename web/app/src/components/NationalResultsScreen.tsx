import { Fragment } from 'react'
import { ExternalLink, Link2Off } from 'lucide-react'
import { formatNumber, formatPercent } from '../domain/format'
import type {
  ElectionCatalog,
  Language,
  NationalParty,
  NationalResults,
} from '../domain/schemas'
import { translate } from '../i18n/translations'
import { LoadingState } from './LoadingState'

interface NationalResultsScreenProps {
  language: Language
  elections: ElectionCatalog[]
  electionId: string
  results: NationalResults | null
  loading: boolean
  error: string | null
  onElectionChange: (electionId: string) => void
}

export function NationalResultsScreen({
  language,
  elections,
  electionId,
  results,
  loading,
  error,
  onElectionChange,
}: NationalResultsScreenProps) {
  return (
    <section className="national-results-screen" aria-labelledby="national-results-title">
      <div className="national-results-toolbar">
        <div>
          <h2 id="national-results-title">{translate(language, 'nationalResultsTitle')}</h2>
          <p>{translate(language, 'nationalResultsSubtitle')}</p>
        </div>
        <label className="national-election-field">
          <span>{translate(language, 'election')}</span>
          <select
            value={electionId}
            aria-label={translate(language, 'election')}
            onChange={(event) => onElectionChange(event.target.value)}
          >
            {elections.map((election) => (
              <option key={election.id} value={election.id}>
                {election.label[language]}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? <LoadingState language={language} /> : null}
      {error ? (
        <div className="national-results-error" role="alert">
          {error}
        </div>
      ) : null}
      {results ? <NationalResultContent language={language} results={results} /> : null}
    </section>
  )
}

function NationalResultContent({
  language,
  results,
}: {
  language: Language
  results: NationalResults
}) {
  const thresholdLabel = formatThreshold(results.threshold.share, language)
  const firstBelowThreshold = results.parties.findIndex((party) => !party.passedThreshold)
  const representedParties = results.parties.filter((party) => party.passedThreshold)

  return (
    <div className="national-results-content">
      <div className="national-summary-grid">
        <SummaryMetric
          label={translate(language, 'validVotes')}
          value={formatNumber(results.totals.validVotes, language)}
        />
        <SummaryMetric
          label={translate(language, 'electoralThreshold')}
          value={thresholdLabel}
        />
        <SummaryMetric
          label={translate(language, 'thresholdMinimum')}
          value={formatNumber(results.threshold.votes, language)}
        />
        <SummaryMetric
          label={translate(language, 'representedLists')}
          value={`${formatNumber(results.totals.representedParties, language)} / ${formatNumber(
            results.totals.contestingParties,
            language,
          )}`}
          valueDirection="ltr"
        />
        <SummaryMetric
          label={translate(language, 'mandates')}
          value={formatNumber(results.totals.mandates, language)}
        />
      </div>

      <div
        className="national-seat-strip"
        role="img"
        aria-label={`${translate(language, 'mandates')}: ${formatNumber(
          results.totals.mandates,
          language,
        )}`}
      >
        {representedParties.map((party) => (
          <span
            key={party.id}
            style={{
              backgroundColor: party.color,
              inlineSize: `${(party.mandates / results.totals.mandates) * 100}%`,
            }}
            title={`${party.names[language]} · ${formatNumber(party.mandates, language)}`}
          />
        ))}
      </div>

      <div className="national-results-meta">
        <span>
          {translate(language, 'candidateLists')} ·{' '}
          {formatNumber(results.totals.contestingParties, language)}
        </span>
        <a href={results.sources.officialResultsUrl} target="_blank" rel="noreferrer">
          <ExternalLink size={15} strokeWidth={2} aria-hidden="true" />
          {translate(language, 'officialResults')}
        </a>
      </div>

      <div className="national-results-table-wrap">
        <table className="national-results-table">
          <thead>
            <tr>
              <th scope="col">
                <span className="national-column-label--desktop">
                  {translate(language, 'candidateLists')}
                </span>
                <span className="national-column-label--mobile">
                  {translate(language, 'candidateListAndBallot')}
                </span>
              </th>
              <th scope="col">{translate(language, 'ballotLetter')}</th>
              <th scope="col">
                <span className="national-column-label--desktop">
                  {translate(language, 'votes')}
                </span>
                <span className="national-column-label--mobile">
                  {translate(language, 'votesAndShare')}
                </span>
              </th>
              <th scope="col">{translate(language, 'share')}</th>
              <th scope="col">{translate(language, 'mandates')}</th>
              <th scope="col">{translate(language, 'wikipedia')}</th>
            </tr>
          </thead>
          <tbody>
            {results.parties.map((party, index) => (
              <Fragment key={party.id}>
                {index === firstBelowThreshold ? (
                  <tr className="national-threshold-row">
                    <td colSpan={6}>
                      <span>{translate(language, 'thresholdDivider')}</span>
                      <strong>{thresholdLabel}</strong>
                      <span>{formatNumber(results.threshold.votes, language)}</span>
                    </td>
                  </tr>
                ) : null}
                <NationalPartyRow language={language} party={party} />
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function NationalPartyRow({
  language,
  party,
}: {
  language: Language
  party: NationalParty
}) {
  return (
    <tr className={party.passedThreshold ? undefined : 'national-party-row--below-threshold'}>
      <th scope="row">
        <div className="national-party-identity">
          <span
            className={`national-party-color${
              party.colorStatus === 'provisional' ? ' national-party-color--provisional' : ''
            }`}
            style={{ backgroundColor: party.color }}
            title={party.colorStatus}
            aria-hidden="true"
          />
          <span className="national-party-name" dir="auto">
            {party.names[language]}
          </span>
          <span className="national-ballot-letter national-ballot-letter--mobile">
            {party.ballotLetter}
          </span>
          {party.colorStatus === 'provisional' ? (
            <span className="national-color-status">
              {translate(language, 'provisionalColor')}
            </span>
          ) : null}
        </div>
      </th>
      <td data-label={translate(language, 'ballotLetter')}>
        <span className="national-ballot-letter">{party.ballotLetter}</span>
      </td>
      <td className="national-number-cell" data-label={translate(language, 'votes')}>
        <span className="national-vote-value">{formatNumber(party.votes, language)}</span>
        <span className="national-vote-share--mobile">
          {formatPercent(party.voteShare, language, 2)}
        </span>
      </td>
      <td className="national-number-cell" data-label={translate(language, 'share')}>
        {formatPercent(party.voteShare, language, 2)}
      </td>
      <td className="national-mandate-cell" data-label={translate(language, 'mandates')}>
        {formatNumber(party.mandates, language)}
      </td>
      <td data-label={translate(language, 'wikipedia')}>
        <div className="national-wikipedia-links">
          <WikipediaButton
            code="HE"
            label={translate(language, 'hebrewWikipedia')}
            missingLabel={translate(language, 'wikipediaUnavailable')}
            url={party.wikipedia.he}
          />
          <WikipediaButton
            code="EN"
            label={translate(language, 'englishWikipedia')}
            missingLabel={translate(language, 'wikipediaUnavailable')}
            url={party.wikipedia.en}
          />
        </div>
      </td>
    </tr>
  )
}

function WikipediaButton({
  code,
  label,
  missingLabel,
  url,
}: {
  code: string
  label: string
  missingLabel: string
  url: string | null
}) {
  if (!url) {
    return (
      <button
        className="national-wikipedia-link national-wikipedia-link--missing"
        type="button"
        disabled
        aria-label={`${label}: ${missingLabel}`}
        title={missingLabel}
      >
        <Link2Off size={13} strokeWidth={2} aria-hidden="true" />
        <span>{code}</span>
      </button>
    )
  }

  return (
    <a
      className="national-wikipedia-link"
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={label}
      title={label}
    >
      <ExternalLink size={13} strokeWidth={2} aria-hidden="true" />
      <span>{code}</span>
    </a>
  )
}

function SummaryMetric({
  label,
  value,
  valueDirection,
}: {
  label: string
  value: string
  valueDirection?: 'ltr' | 'rtl'
}) {
  return (
    <div>
      <span>{label}</span>
      <strong dir={valueDirection}>{value}</strong>
    </div>
  )
}

function formatThreshold(value: number, language: Language): string {
  const percent = value * 100
  return formatPercent(value, language, Number.isInteger(percent) ? 0 : 2)
}
