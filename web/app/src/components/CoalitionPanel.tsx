import type { CSSProperties } from 'react'
import { formatPercent } from '../domain/format'
import { partyGradientColor, PARTY_MAP_ZERO_COLOR } from '../domain/partyMap'
import type { Language, Party } from '../domain/schemas'
import { translate } from '../i18n/translations'

interface CoalitionPanelProps {
  language: Language
  anchorParty: Party | null
  upperBoundShare: number
}

export function CoalitionPanel({
  language,
  anchorParty,
  upperBoundShare,
}: CoalitionPanelProps) {
  const anchorColor = anchorParty?.color ?? '#69736d'
  const midpoint = upperBoundShare / 2
  const legendStyle = {
    '--coalition-zero': PARTY_MAP_ZERO_COLOR,
    '--coalition-color': anchorColor,
    '--coalition-color-quarter': partyGradientColor(anchorColor, 0.25, 1),
    '--coalition-color-half': partyGradientColor(anchorColor, 0.5, 1),
    '--coalition-color-three-quarter': partyGradientColor(anchorColor, 0.75, 1),
  } as CSSProperties

  return (
    <section
      className="coalition-panel"
      aria-label={translate(language, 'coalitionMapControls')}
    >
      <div className="coalition-legend" style={legendStyle}>
        <span className="coalition-legend__title">
          {translate(language, 'coalitionVoteShare')}
        </span>
        <span className="coalition-legend__ramp" aria-hidden="true" />
        <div className="coalition-legend__labels" dir="ltr">
          <span>{formatPercent(0, language)}</span>
          <span>{formatPercent(midpoint, language)}</span>
          <span>&gt;{formatPercent(upperBoundShare, language)}</span>
        </div>
      </div>
    </section>
  )
}
