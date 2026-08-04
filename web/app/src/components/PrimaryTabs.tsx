import { BarChart3, Handshake, Map, Scale, Target } from 'lucide-react'
import type { Language } from '../domain/schemas'
import { translate } from '../i18n/translations'

export type AppView = 'map' | 'party-map' | 'party-comparison' | 'coalition' | 'national'

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
      <button
        type="button"
        className={activeView === 'map' ? 'primary-tab primary-tab--active' : 'primary-tab'}
        aria-label={translate(language, 'mapView')}
        aria-current={activeView === 'map' ? 'page' : undefined}
        onClick={() => onChange('map')}
      >
        <Map size={17} strokeWidth={2} aria-hidden="true" />
        <span className="primary-tab__label">{translate(language, 'mapView')}</span>
        <span className="primary-tab__label-short" aria-hidden="true">
          {translate(language, 'mapViewShort')}
        </span>
      </button>
      <button
        type="button"
        className={
          activeView === 'party-map' ? 'primary-tab primary-tab--active' : 'primary-tab'
        }
        aria-label={translate(language, 'partyMapView')}
        aria-current={activeView === 'party-map' ? 'page' : undefined}
        onClick={() => onChange('party-map')}
      >
        <Target size={17} strokeWidth={2} aria-hidden="true" />
        <span className="primary-tab__label">{translate(language, 'partyMapView')}</span>
        <span className="primary-tab__label-short" aria-hidden="true">
          {translate(language, 'partyMapViewShort')}
        </span>
      </button>
      <button
        type="button"
        className={
          activeView === 'party-comparison'
            ? 'primary-tab primary-tab--active'
            : 'primary-tab'
        }
        aria-label={translate(language, 'partyComparisonView')}
        aria-current={activeView === 'party-comparison' ? 'page' : undefined}
        onClick={() => onChange('party-comparison')}
      >
        <Scale size={17} strokeWidth={2} aria-hidden="true" />
        <span className="primary-tab__label">
          {translate(language, 'partyComparisonView')}
        </span>
        <span className="primary-tab__label-short" aria-hidden="true">
          {translate(language, 'partyComparisonViewShort')}
        </span>
      </button>
      <button
        type="button"
        className={
          activeView === 'coalition' ? 'primary-tab primary-tab--active' : 'primary-tab'
        }
        aria-label={translate(language, 'coalitionView')}
        aria-current={activeView === 'coalition' ? 'page' : undefined}
        onClick={() => onChange('coalition')}
      >
        <Handshake size={17} strokeWidth={2} aria-hidden="true" />
        <span className="primary-tab__label">{translate(language, 'coalitionView')}</span>
        <span className="primary-tab__label-short" aria-hidden="true">
          {translate(language, 'coalitionViewShort')}
        </span>
      </button>
      <button
        type="button"
        className={
          activeView === 'national' ? 'primary-tab primary-tab--active' : 'primary-tab'
        }
        aria-label={translate(language, 'nationalView')}
        aria-current={activeView === 'national' ? 'page' : undefined}
        onClick={() => onChange('national')}
      >
        <BarChart3 size={17} strokeWidth={2} aria-hidden="true" />
        <span className="primary-tab__label">{translate(language, 'nationalView')}</span>
        <span className="primary-tab__label-short" aria-hidden="true">
          {translate(language, 'nationalViewShort')}
        </span>
      </button>
    </nav>
  )
}
