import type { CSSProperties } from 'react'
import { UNMAPPED_GEOGRAPHY_COLOR } from '../domain/color'
import {
  PARTY_COMPARISON_NO_VOTES_COLOR,
  PARTY_COMPARISON_TIE_COLOR,
} from '../domain/partyComparison'
import type { Language, Party } from '../domain/schemas'
import { translate } from '../i18n/translations'

interface PartyComparisonPanelProps {
  language: Language
  parties: Party[]
  firstPartyId: string | null
  secondPartyId: string | null
  onFirstPartyChange: (partyId: string) => void
  onSecondPartyChange: (partyId: string) => void
}

export function PartyComparisonPanel({
  language,
  parties,
  firstPartyId,
  secondPartyId,
  onFirstPartyChange,
  onSecondPartyChange,
}: PartyComparisonPanelProps) {
  const firstParty = parties.find((party) => party.id === firstPartyId) ?? null
  const secondParty = parties.find((party) => party.id === secondPartyId) ?? null
  const legendStyle = {
    '--comparison-first': firstParty?.color ?? '#69736d',
    '--comparison-second': secondParty?.color ?? '#69736d',
    '--comparison-tie': PARTY_COMPARISON_TIE_COLOR,
    '--comparison-no-votes': PARTY_COMPARISON_NO_VOTES_COLOR,
    '--comparison-no-result': UNMAPPED_GEOGRAPHY_COLOR,
  } as CSSProperties

  return (
    <section
      className="party-comparison-panel"
      aria-label={translate(language, 'partyComparisonControls')}
    >
      <PartySelector
        language={language}
        label={translate(language, 'partyComparisonFirst')}
        parties={parties}
        selectedParty={firstParty}
        excludedPartyId={secondPartyId}
        onChange={onFirstPartyChange}
      />
      <PartySelector
        language={language}
        label={translate(language, 'partyComparisonSecond')}
        parties={parties}
        selectedParty={secondParty}
        excludedPartyId={firstPartyId}
        onChange={onSecondPartyChange}
      />

      <div className="party-comparison-legend" style={legendStyle}>
        <span className="party-comparison-legend__title">
          {translate(language, 'partyComparisonBalance')}
        </span>
        <span className="party-comparison-legend__ramp" aria-hidden="true" />
        <div className="party-comparison-legend__labels">
          <span dir="auto">{firstParty?.names[language] ?? ''}</span>
          <span>{translate(language, 'partyComparisonTie')}</span>
          <span dir="auto">{secondParty?.names[language] ?? ''}</span>
        </div>
        <div className="party-comparison-legend__states">
          <span>
            <i className="party-comparison-legend__no-votes" aria-hidden="true" />
            {translate(language, 'partyComparisonNoVotes')}
          </span>
          <span>
            <i className="party-comparison-legend__no-result" aria-hidden="true" />
            {translate(language, 'partyMapNoResult')}
          </span>
        </div>
      </div>
    </section>
  )
}

interface PartySelectorProps {
  language: Language
  label: string
  parties: Party[]
  selectedParty: Party | null
  excludedPartyId: string | null
  onChange: (partyId: string) => void
}

function PartySelector({
  language,
  label,
  parties,
  selectedParty,
  excludedPartyId,
  onChange,
}: PartySelectorProps) {
  return (
    <label className="party-map-field">
      <span>{label}</span>
      <div className="party-map-select-wrap">
        <span
          className="party-swatch"
          style={{ backgroundColor: selectedParty?.color ?? '#69736d' }}
          aria-hidden="true"
        />
        <select
          value={selectedParty?.id ?? ''}
          disabled={parties.length < 2}
          aria-label={label}
          onChange={(event) => onChange(event.target.value)}
        >
          {parties.map((party) => (
            <option
              key={party.id}
              value={party.id}
              dir="auto"
              disabled={party.id === excludedPartyId}
            >
              {party.names[language]} ({party.ballotLetter})
            </option>
          ))}
        </select>
      </div>
    </label>
  )
}
