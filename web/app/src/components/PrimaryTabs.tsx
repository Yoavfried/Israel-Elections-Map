import { BarChart3, Handshake, Map, Scale, Target } from 'lucide-react'
import type { Language } from '../domain/schemas'
import { translate } from '../i18n/translations'
import type { TranslationKey } from '../i18n/translations'

export type AppView = 'map' | 'party-map' | 'party-comparison' | 'coalition' | 'national'

export const PRIMARY_VIEW_OPTIONS: ReadonlyArray<{
  value: AppView
  labelKey: TranslationKey
  shortLabelKey: TranslationKey
  icon: typeof Map
}> = [
  { value: 'map', labelKey: 'mapView', shortLabelKey: 'mapViewShort', icon: Map },
  {
    value: 'party-map',
    labelKey: 'partyMapView',
    shortLabelKey: 'partyMapViewShort',
    icon: Target,
  },
  {
    value: 'party-comparison',
    labelKey: 'partyComparisonView',
    shortLabelKey: 'partyComparisonViewShort',
    icon: Scale,
  },
  {
    value: 'coalition',
    labelKey: 'coalitionView',
    shortLabelKey: 'coalitionViewShort',
    icon: Handshake,
  },
  {
    value: 'national',
    labelKey: 'nationalView',
    shortLabelKey: 'nationalViewShort',
    icon: BarChart3,
  },
]

interface PrimaryTabsProps {
  activeView: AppView
  language: Language
  onChange: (view: AppView) => void
}

export function PrimaryTabs({ activeView, language, onChange }: PrimaryTabsProps) {
  return (
    <nav
      className="primary-tabs"
      aria-label={translate(language, 'primaryNavigation')}
    >
      {PRIMARY_VIEW_OPTIONS.map((option) => {
        const Icon = option.icon
        const active = activeView === option.value
        return (
          <button
            key={option.value}
            type="button"
            className={active ? 'primary-tab primary-tab--active' : 'primary-tab'}
            aria-label={translate(language, option.labelKey)}
            aria-current={active ? 'page' : undefined}
            onClick={() => onChange(option.value)}
          >
            <Icon size={17} strokeWidth={2} aria-hidden="true" />
            <span className="primary-tab__label">
              {translate(language, option.labelKey)}
            </span>
            <span className="primary-tab__label-short" aria-hidden="true">
              {translate(language, option.shortLabelKey)}
            </span>
          </button>
        )
      })}
    </nav>
  )
}
