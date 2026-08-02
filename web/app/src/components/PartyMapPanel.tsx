import type { CSSProperties } from 'react'
import { formatPercent } from '../domain/format'
import { partyGradientColor, PARTY_MAP_ZERO_COLOR } from '../domain/partyMap'
import type { Language, Party } from '../domain/schemas'
import { translate } from '../i18n/translations'

interface PartyMapPanelProps {
  language: Language
  parties: Party[]
  selectedPartyId: string | null
  upperBoundShare: number
  onPartyChange: (partyId: string) => void
}

export function PartyMapPanel({
  language,
  parties,
  selectedPartyId,
  upperBoundShare,
  onPartyChange,
}: PartyMapPanelProps) {
  const selectedParty = parties.find((party) => party.id === selectedPartyId) ?? null
  const midpoint = upperBoundShare / 2
  const legendStyle = {
    '--party-map-zero': PARTY_MAP_ZERO_COLOR,
    '--party-map-color': selectedParty?.color ?? '#69736d',
    '--party-map-color-quarter': partyGradientColor(
      selectedParty?.color ?? '#69736d',
      0.25,
      1,
    ),
    '--party-map-color-half': partyGradientColor(
      selectedParty?.color ?? '#69736d',
      0.5,
      1,
    ),
    '--party-map-color-three-quarter': partyGradientColor(
      selectedParty?.color ?? '#69736d',
      0.75,
      1,
    ),
  } as CSSProperties

  return (
    <section
      className="party-map-panel"
      aria-label={translate(language, 'partyMapControls')}
    >
      <label className="party-map-field">
        <span>{translate(language, 'partyMapParty')}</span>
        <div className="party-map-select-wrap">
          <span
            className="party-swatch"
            style={{ backgroundColor: selectedParty?.color ?? '#69736d' }}
            aria-hidden="true"
          />
          <select
            value={selectedPartyId ?? ''}
            disabled={parties.length === 0}
            aria-label={translate(language, 'partyMapParty')}
            onChange={(event) => onPartyChange(event.target.value)}
          >
            {parties.map((party) => (
              <option key={party.id} value={party.id}>
                {party.names[language]} ({party.ballotLetter})
              </option>
            ))}
          </select>
        </div>
      </label>

      <div className="party-map-legend" style={legendStyle}>
        <span className="party-map-legend__title">
          {translate(language, 'partyMapVoteShare')}
        </span>
        <span className="party-map-legend__ramp" aria-hidden="true" />
        <div className="party-map-legend__labels" dir="ltr">
          <span>{formatPercent(0, language)}</span>
          <span>{formatPercent(midpoint, language)}</span>
          <span
            aria-label={`${translate(language, 'partyMapUpperBoundAria')} ${formatPercent(
              upperBoundShare,
              language,
            )}`}
          >
            &gt;{formatPercent(upperBoundShare, language)}
          </span>
        </div>
        <span className="party-map-legend__missing">
          <span aria-hidden="true" />
          {translate(language, 'partyMapNoResult')}
        </span>
      </div>
    </section>
  )
}
