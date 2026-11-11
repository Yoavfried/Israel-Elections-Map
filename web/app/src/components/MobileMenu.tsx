import { CircleDot, CodeXml, House, Layers, Map, Menu, Shapes, Shield, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { PartyMapDisplayMode } from '../domain/partyMap'
import type {
  BasemapMode,
  ElectionCatalog,
  GeographyMode,
  GeographyModeCatalog,
  Language,
  Party,
} from '../domain/schemas'
import { translate } from '../i18n/translations'
import { PRIMARY_VIEW_OPTIONS } from './PrimaryTabs'
import type { AppView } from './PrimaryTabs'

interface MobileMenuProps {
  language: Language
  activeView: AppView
  elections: ElectionCatalog[]
  geographyModes: GeographyModeCatalog[]
  electionId: string
  geographyMode: GeographyMode
  basemapMode: BasemapMode
  partyMapDisplayMode: PartyMapDisplayMode
  parties: Party[]
  selectedPartyId: string | null
  firstPartyId: string | null
  secondPartyId: string | null
  onViewChange: (view: AppView) => void
  onElectionChange: (electionId: string) => void
  onGeographyModeChange: (mode: GeographyMode) => void
  onBasemapModeChange: (mode: BasemapMode) => void
  onPartyMapDisplayModeChange: (mode: PartyMapDisplayMode) => void
  onPartyChange: (partyId: string) => void
  onFirstPartyChange: (partyId: string) => void
  onSecondPartyChange: (partyId: string) => void
}

const menuId = 'mobile-navigation-menu'

export function MobileMenu({
  language,
  activeView,
  elections,
  geographyModes,
  electionId,
  geographyMode,
  basemapMode,
  partyMapDisplayMode,
  parties,
  selectedPartyId,
  firstPartyId,
  secondPartyId,
  onViewChange,
  onElectionChange,
  onGeographyModeChange,
  onBasemapModeChange,
  onPartyMapDisplayModeChange,
  onPartyChange,
  onFirstPartyChange,
  onSecondPartyChange,
}: MobileMenuProps) {
  const [open, setOpen] = useState(false)
  const isGeographicView = activeView !== 'national'

  useEffect(() => {
    if (!open) return

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [open])

  const selectedParty = parties.find((party) => party.id === selectedPartyId) ?? null
  const firstParty = parties.find((party) => party.id === firstPartyId) ?? null
  const secondParty = parties.find((party) => party.id === secondPartyId) ?? null
  const toggleLabel = translate(language, open ? 'mobileMenuClose' : 'mobileMenuOpen')

  return (
    <div className="mobile-menu">
      <button
        className="mobile-menu__trigger"
        type="button"
        aria-label={toggleLabel}
        title={toggleLabel}
        aria-controls={menuId}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        {open ? (
          <X size={23} strokeWidth={2.2} aria-hidden="true" />
        ) : (
          <Menu size={23} strokeWidth={2.2} aria-hidden="true" />
        )}
      </button>

      <button
        className="mobile-menu__scrim"
        type="button"
        aria-label={translate(language, 'mobileMenuClose')}
        tabIndex={open ? 0 : -1}
        hidden={!open}
        onClick={() => setOpen(false)}
      />

      <div
        id={menuId}
        className="mobile-menu__panel"
        dir={language === 'he' ? 'rtl' : 'ltr'}
        role="dialog"
        aria-modal="true"
        aria-label={translate(language, 'mobileMenuTitle')}
        hidden={!open}
      >
        <section className="mobile-menu__section">
          <h2>{translate(language, 'primaryNavigation')}</h2>
          <nav className="mobile-menu__views" aria-label={translate(language, 'primaryNavigation')}>
            {PRIMARY_VIEW_OPTIONS.map((option) => {
              const Icon = option.icon
              const active = activeView === option.value
              return (
                <button
                  key={option.value}
                  type="button"
                  className={active ? 'is-active' : undefined}
                  aria-current={active ? 'page' : undefined}
                  onClick={() => onViewChange(option.value)}
                >
                  <Icon size={22} strokeWidth={2.2} aria-hidden="true" />
                  <span>{translate(language, option.labelKey)}</span>
                </button>
              )
            })}
          </nav>
        </section>

        {activeView !== 'national' ? (
          <section className="mobile-menu__section mobile-menu__fields">
            <label className="field">
              <span>{translate(language, 'election')}</span>
              <select value={electionId} onChange={(event) => onElectionChange(event.target.value)}>
                {elections.map((election) => (
                  <option key={election.id} value={election.id}>
                    {election.label[language]}
                  </option>
                ))}
              </select>
            </label>

            {isGeographicView ? (
              <label className="field">
                <span>{translate(language, 'geography')}</span>
                <select
                  value={geographyMode}
                  onChange={(event) => onGeographyModeChange(event.target.value as GeographyMode)}
                >
                  {geographyModes.map((mode) => (
                    <option key={mode.id} value={mode.id}>
                      {mode.label[language]}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </section>
        ) : null}

        {activeView === 'party-map' ? (
          <section className="mobile-menu__section">
            <PartySelect
              language={language}
              label={translate(language, 'partyMapParty')}
              parties={parties}
              selectedParty={selectedParty}
              excludedPartyId={null}
              onChange={onPartyChange}
            />
          </section>
        ) : null}

        {activeView === 'party-comparison' ? (
          <section className="mobile-menu__section mobile-menu__party-fields">
            <PartySelect
              language={language}
              label={translate(language, 'partyComparisonFirst')}
              parties={parties}
              selectedParty={firstParty}
              excludedPartyId={secondPartyId}
              onChange={onFirstPartyChange}
            />
            <PartySelect
              language={language}
              label={translate(language, 'partyComparisonSecond')}
              parties={parties}
              selectedParty={secondParty}
              excludedPartyId={firstPartyId}
              onChange={onSecondPartyChange}
            />
          </section>
        ) : null}

        {isGeographicView ? (
          <section className="mobile-menu__section">
            <h2>{translate(language, 'basemapLabel')}</h2>
            <div className="mobile-menu__segmented" role="group" aria-label={translate(language, 'basemapLabel')}>
              <button
                type="button"
                className={basemapMode === 'neutral' ? 'is-active' : undefined}
                aria-pressed={basemapMode === 'neutral'}
                onClick={() => onBasemapModeChange('neutral')}
              >
                <Layers size={18} strokeWidth={2} aria-hidden="true" />
                <span>{translate(language, 'basemapNeutral')}</span>
              </button>
              <button
                type="button"
                className={basemapMode === 'vector' ? 'is-active' : undefined}
                aria-pressed={basemapMode === 'vector'}
                onClick={() => onBasemapModeChange('vector')}
              >
                <Map size={18} strokeWidth={2} aria-hidden="true" />
                <span>{translate(language, 'basemapVector')}</span>
              </button>
            </div>
            {activeView === 'party-map' ? (
              <>
                <h2>{translate(language, 'partyMapDisplay')}</h2>
                <div
                  className="mobile-menu__segmented"
                  role="group"
                  aria-label={translate(language, 'partyMapDisplay')}
                >
                  <button
                    type="button"
                    className={partyMapDisplayMode === 'areas' ? 'is-active' : undefined}
                    aria-pressed={partyMapDisplayMode === 'areas'}
                    onClick={() => onPartyMapDisplayModeChange('areas')}
                  >
                    <Shapes size={18} strokeWidth={2} aria-hidden="true" />
                    <span>{translate(language, 'partyMapAreas')}</span>
                  </button>
                  <button
                    type="button"
                    className={partyMapDisplayMode === 'circles' ? 'is-active' : undefined}
                    aria-pressed={partyMapDisplayMode === 'circles'}
                    onClick={() => onPartyMapDisplayModeChange('circles')}
                  >
                    <CircleDot size={18} strokeWidth={2} aria-hidden="true" />
                    <span>{translate(language, 'partyMapCircles')}</span>
                  </button>
                </div>
              </>
            ) : null}
          </section>
        ) : null}

        <section className="mobile-menu__section">
          <h2>{translate(language, 'mobileMenuResources')}</h2>
          <div className="mobile-menu__links">
            <a href="https://yoavfried.com/">
              <House size={18} strokeWidth={2} aria-hidden="true" />
              <span>{translate(language, 'portfolioAction')}</span>
            </a>
            <a href="https://github.com/Yoavfried/israel-election-map" target="_blank" rel="noreferrer">
              <CodeXml size={18} strokeWidth={2} aria-hidden="true" />
              <span>{translate(language, 'repositoryAction')}</span>
            </a>
            <a href={`${import.meta.env.BASE_URL}privacy.html?lang=${language}`}>
              <Shield size={18} strokeWidth={2} aria-hidden="true" />
              <span>{translate(language, 'privacyAction')}</span>
            </a>
          </div>
        </section>
      </div>
    </div>
  )
}

interface PartySelectProps {
  language: Language
  label: string
  parties: Party[]
  selectedParty: Party | null
  excludedPartyId: string | null
  onChange: (partyId: string) => void
}

function PartySelect({
  language,
  label,
  parties,
  selectedParty,
  excludedPartyId,
  onChange,
}: PartySelectProps) {
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
          disabled={parties.length === 0}
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
