import { BarChart3, Map } from 'lucide-react'
import type { Language } from '../domain/schemas'
import { translate } from '../i18n/translations'

export type AppView = 'map' | 'national'

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
        aria-current={activeView === 'map' ? 'page' : undefined}
        onClick={() => onChange('map')}
      >
        <Map size={17} strokeWidth={2} aria-hidden="true" />
        <span>{translate(language, 'mapView')}</span>
      </button>
      <button
        type="button"
        className={
          activeView === 'national' ? 'primary-tab primary-tab--active' : 'primary-tab'
        }
        aria-current={activeView === 'national' ? 'page' : undefined}
        onClick={() => onChange('national')}
      >
        <BarChart3 size={17} strokeWidth={2} aria-hidden="true" />
        <span>{translate(language, 'nationalView')}</span>
      </button>
    </nav>
  )
}
