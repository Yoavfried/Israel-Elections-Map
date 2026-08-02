import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { ControlPanel } from './components/ControlPanel'
import { DetailsPanel } from './components/DetailsPanel'
import { EnvelopeSummary } from './components/EnvelopeSummary'
import { GeographySearch } from './components/GeographySearch'
import { LoadingState } from './components/LoadingState'
import { NationalResultsScreen } from './components/NationalResultsScreen'
import { PartyComparisonPanel } from './components/PartyComparisonPanel'
import { PartyMapPanel } from './components/PartyMapPanel'
import { PrimaryTabs } from './components/PrimaryTabs'
import type { AppView } from './components/PrimaryTabs'
import {
  loadCatalog,
  loadElectionResults,
  loadGeographySearchIndex,
  loadNationalResults,
  resolveDataUrl,
} from './data/client'
import type { AddressSearchMatch } from './domain/addressSearch'
import type {
  AppCatalog,
  ElectionResults,
  GeographyMode,
  GeographySearchIndex,
  GeographySearchItem,
  Language,
  NationalResults,
} from './domain/schemas'
import { partyVoteShareUpperBound, rankPartiesForMap } from './domain/partyMap'
import { translate } from './i18n/translations'
import { loadPreferences, savePreferences } from './state/preferences'

const MapCanvas = lazy(() => import('./components/MapCanvas'))

type Loadable<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; message: string }

const storage = safeStorage()

export default function App() {
  const [preferences, setPreferences] = useState(() =>
    loadPreferences(storage, navigator.language),
  )
  const [catalogState, setCatalogState] = useState<Loadable<AppCatalog>>({ status: 'loading' })
  const [resultsState, setResultsState] = useState<Loadable<ElectionResults>>({ status: 'loading' })
  const [nationalResultsState, setNationalResultsState] = useState<Loadable<NationalResults>>({
    status: 'loading',
  })
  const [searchState, setSearchState] = useState<Loadable<GeographySearchIndex>>({
    status: 'loading',
  })
  const [activeView, setActiveView] = useState<AppView>('map')
  const [selectedPartyId, setSelectedPartyId] = useState<string | null>(null)
  const [comparisonPartyIds, setComparisonPartyIds] = useState<
    [string | null, string | null]
  >([null, null])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedSearchItem, setSelectedSearchItem] =
    useState<GeographySearchItem | null>(null)
  const [selectedAddress, setSelectedAddress] =
    useState<AddressSearchMatch | null>(null)
  const [focusRequest, setFocusRequest] = useState<{
    id: string
    bounds: GeographySearchItem['bounds']
    requestId: number
  } | null>(null)
  const { language, electionId, geographyMode, basemapMode } = preferences
  const isGeographicView =
    activeView === 'map' ||
    activeView === 'party-map' ||
    activeView === 'party-comparison'

  useEffect(() => {
    let active = true
    loadCatalog()
      .then((catalog) => {
        if (!active) {
          return
        }
        setCatalogState({ status: 'ready', data: catalog })
        setPreferences((currentPreferences) => {
          if (catalog.elections.some((election) => election.id === currentPreferences.electionId)) {
            return currentPreferences
          }
          const nextPreferences = {
            ...currentPreferences,
            electionId: catalog.elections[0].id,
          }
          savePreferences(storage, nextPreferences)
          return nextPreferences
        })
      })
      .catch((error: unknown) => {
        if (active) {
          setCatalogState({ status: 'error', message: errorMessage(error) })
        }
      })
    return () => {
      active = false
    }
  }, [])

  const catalog = catalogState.status === 'ready' ? catalogState.data : null
  const selectedElection = catalog?.elections.find((election) => election.id === electionId)
  const selectedMode = catalog?.geographyModes.find((mode) => mode.id === geographyMode)
  const selectedGeography = selectedElection?.geographiesByMode[geographyMode]

  useEffect(() => {
    if (!selectedElection || !isGeographicView) {
      return
    }
    let active = true
    setResultsState({ status: 'loading' })
    loadElectionResults(
      selectedElection.id,
      geographyMode,
      selectedElection.resultUrls[geographyMode],
    )
      .then((results) => {
        if (active) {
          setResultsState({ status: 'ready', data: results })
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setResultsState({ status: 'error', message: errorMessage(error) })
        }
      })
    return () => {
      active = false
    }
  }, [geographyMode, isGeographicView, selectedElection])

  useEffect(() => {
    if (!selectedElection || activeView !== 'national') {
      return
    }
    let active = true
    setNationalResultsState({ status: 'loading' })
    loadNationalResults(selectedElection.id, selectedElection.resultUrls.national)
      .then((nationalResults) => {
        if (active) {
          setNationalResultsState({ status: 'ready', data: nationalResults })
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setNationalResultsState({ status: 'error', message: errorMessage(error) })
        }
      })
    return () => {
      active = false
    }
  }, [activeView, selectedElection])

  useEffect(() => {
    if (!selectedElection || !isGeographicView) {
      return
    }
    let active = true
    setSearchState({ status: 'loading' })
    loadGeographySearchIndex(selectedElection.id, selectedElection.resultUrls.search)
      .then((searchIndex) => {
        if (active) {
          setSearchState({ status: 'ready', data: searchIndex })
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setSearchState({ status: 'error', message: errorMessage(error) })
        }
      })
    return () => {
      active = false
    }
  }, [isGeographicView, selectedElection])

  useEffect(() => {
    document.documentElement.lang = language
    document.documentElement.dir = language === 'he' ? 'rtl' : 'ltr'
    document.title = translate(language, 'appTitle')
  }, [language])

  const results =
    resultsState.status === 'ready' &&
    resultsState.data.electionId === electionId &&
    resultsState.data.geographyMode === geographyMode
      ? resultsState.data
      : null
  const resultsById = useMemo(
    () =>
      new Map(
        [...(results?.records ?? []), ...(results?.envelope ? [results.envelope] : [])].map(
          (record) => [record.id, record],
        ),
      ),
    [results],
  )
  const selectedRecord = selectedId ? resultsById.get(selectedId) ?? null : null
  const searchIndex =
    searchState.status === 'ready' && searchState.data.electionId === electionId
      ? searchState.data
      : null
  const nationalResults =
    nationalResultsState.status === 'ready' &&
    nationalResultsState.data.electionId === electionId
      ? nationalResultsState.data
      : null
  const partyMapParties = useMemo(
    () =>
      results
        ? rankPartiesForMap(results.parties, results.records, results.envelope, language)
        : [],
    [language, results],
  )
  const effectivePartyId = partyMapParties.some((party) => party.id === selectedPartyId)
    ? selectedPartyId
    : partyMapParties[0]?.id ?? null
  const selectedParty =
    results?.parties.find((party) => party.id === effectivePartyId) ?? null
  const effectiveComparisonFirstId = partyMapParties.some(
    (party) => party.id === comparisonPartyIds[0],
  )
    ? comparisonPartyIds[0]
    : partyMapParties[0]?.id ?? null
  const effectiveComparisonSecondId = partyMapParties.some(
    (party) =>
      party.id === comparisonPartyIds[1] && party.id !== effectiveComparisonFirstId,
  )
    ? comparisonPartyIds[1]
    : partyMapParties.find((party) => party.id !== effectiveComparisonFirstId)?.id ?? null
  const comparisonFirstParty =
    partyMapParties.find((party) => party.id === effectiveComparisonFirstId) ?? null
  const comparisonSecondParty =
    partyMapParties.find((party) => party.id === effectiveComparisonSecondId) ?? null
  const partyMapUpperBoundShare =
    results && effectivePartyId
      ? partyVoteShareUpperBound(results.records, effectivePartyId)
      : 0
  const partyMapPresentation = useMemo(
    () =>
      activeView === 'party-map' && selectedParty
        ? {
            partyId: selectedParty.id,
            color: selectedParty.color,
            upperBoundShare: partyMapUpperBoundShare,
          }
        : null,
    [activeView, partyMapUpperBoundShare, selectedParty],
  )
  const partyComparisonPresentation = useMemo(
    () =>
      activeView === 'party-comparison' && comparisonFirstParty && comparisonSecondParty
        ? {
            firstPartyId: comparisonFirstParty.id,
            firstColor: comparisonFirstParty.color,
            secondPartyId: comparisonSecondParty.id,
            secondColor: comparisonSecondParty.color,
          }
        : null,
    [activeView, comparisonFirstParty, comparisonSecondParty],
  )

  const updatePreferences = (nextPreferences: typeof preferences) => {
    setPreferences(nextPreferences)
    savePreferences(storage, nextPreferences)
  }
  const handleElectionChange = (nextElectionId: string) => {
    setSelectedId(null)
    setSelectedSearchItem(null)
    setSelectedAddress(null)
    setFocusRequest(null)
    setSelectedPartyId(null)
    setComparisonPartyIds([null, null])
    updatePreferences({ ...preferences, electionId: nextElectionId })
  }
  const handleGeographyChange = (nextMode: GeographyMode) => {
    setSelectedId(null)
    setSelectedSearchItem(null)
    setSelectedAddress(null)
    setFocusRequest(null)
    updatePreferences({ ...preferences, geographyMode: nextMode })
  }
  const handleBasemapChange = (nextMode: typeof basemapMode) => {
    updatePreferences({ ...preferences, basemapMode: nextMode })
  }
  const handleComparisonFirstChange = (partyId: string) => {
    setComparisonPartyIds([
      partyId,
      effectiveComparisonSecondId && effectiveComparisonSecondId !== partyId
        ? effectiveComparisonSecondId
        : partyMapParties.find((party) => party.id !== partyId)?.id ?? null,
    ])
  }
  const handleComparisonSecondChange = (partyId: string) => {
    setComparisonPartyIds([
      effectiveComparisonFirstId && effectiveComparisonFirstId !== partyId
        ? effectiveComparisonFirstId
        : partyMapParties.find((party) => party.id !== partyId)?.id ?? null,
      partyId,
    ])
  }
  const toggleLanguage = () => {
    const nextLanguage: Language = language === 'en' ? 'he' : 'en'
    updatePreferences({ ...preferences, language: nextLanguage })
  }
  const handleViewChange = (nextView: AppView) => {
    setSelectedId(null)
    setSelectedSearchItem(null)
    setSelectedAddress(null)
    setFocusRequest(null)
    setActiveView(nextView)
  }
  const clearMapSelection = () => {
    setSelectedId(null)
    setSelectedSearchItem(null)
    setSelectedAddress(null)
    setFocusRequest(null)
  }
  const handleMapSelect = (id: string | null) => {
    setSelectedId(id)
    setSelectedSearchItem(null)
    setSelectedAddress(null)
    setFocusRequest(null)
  }
  const handleSearchSelect = (item: GeographySearchItem) => {
    setSelectedId(item.id)
    setSelectedSearchItem(item)
    setSelectedAddress(null)
    setFocusRequest((current) => ({
      id: item.id,
      bounds: item.bounds,
      requestId: (current?.requestId ?? 0) + 1,
    }))
    if (item.geographyMode !== geographyMode) {
      updatePreferences({ ...preferences, geographyMode: item.geographyMode })
    }
  }
  const handleAddressSearchSelect = (match: AddressSearchMatch) => {
    setSelectedId(match.area.id)
    setSelectedSearchItem(match.area)
    setSelectedAddress(match)
    setFocusRequest((current) => ({
      id: match.id,
      bounds: match.area.bounds,
      requestId: (current?.requestId ?? 0) + 1,
    }))
    if (geographyMode !== 'statistical-area') {
      updatePreferences({ ...preferences, geographyMode: 'statistical-area' })
    }
  }

  if (catalogState.status === 'loading') {
    return <LoadingState language={language} />
  }
  if (
    catalogState.status === 'error' ||
    !catalog ||
    !selectedElection ||
    !selectedMode ||
    !selectedGeography
  ) {
    return (
      <main className="fatal-state" role="alert">
        <h1>{translate(language, 'dataError')}</h1>
        <p>{catalogState.status === 'error' ? catalogState.message : 'Invalid catalog selection.'}</p>
      </main>
    )
  }

  return (
    <main className="app-shell" data-language={language} data-view={activeView}>
      <header className="app-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">IL</span>
          <div>
            <h1>{translate(language, 'appTitle')}</h1>
            <p>{translate(language, 'appSubtitle')}</p>
          </div>
        </div>
        <PrimaryTabs
          activeView={activeView}
          language={language}
          onChange={handleViewChange}
        />
        <button className="language-toggle" type="button" onClick={toggleLanguage}>
          {translate(language, 'languageAction')}
        </button>
      </header>

      {isGeographicView ? (
        <div className="map-stage">
          {resultsState.status === 'ready' && results ? (
            <Suspense fallback={<LoadingState language={language} kind="map" />}>
              <MapCanvas
                language={language}
                geographyMode={geographyMode}
                geometryUrl={resolveDataUrl(selectedGeography.geometryUrl)}
                markerGeometryUrl={resolveDataUrl(selectedGeography.markerGeometryUrl)}
                backdropGeometryUrl={
                  selectedGeography.backdropGeometryUrl
                    ? resolveDataUrl(selectedGeography.backdropGeometryUrl)
                    : null
                }
                basemapMaskGeometryUrl={
                  selectedGeography.basemapMaskGeometryUrl
                    ? resolveDataUrl(selectedGeography.basemapMaskGeometryUrl)
                    : null
                }
                mapContextGeometryUrl={
                  selectedGeography.mapContextGeometryUrl
                    ? resolveDataUrl(selectedGeography.mapContextGeometryUrl)
                    : null
                }
                bounds={catalog.bounds}
                records={results.records}
                parties={results.parties}
                hiddenGeographyIds={results.hiddenGeographyIds}
                selectedId={selectedId}
                focusRequest={focusRequest}
                addressMarker={
                  selectedAddress
                    ? {
                        coordinates: selectedAddress.coordinates,
                        label: selectedAddress.label,
                      }
                    : null
                }
                partyMap={partyMapPresentation}
                partyComparison={partyComparisonPresentation}
                basemapMode={basemapMode}
                onBasemapModeChange={handleBasemapChange}
                onSelect={handleMapSelect}
              />
            </Suspense>
          ) : resultsState.status === 'error' ? (
            <div className="map-error" role="alert">
              <strong>{translate(language, 'dataError')}</strong>
              <span>{resultsState.message}</span>
            </div>
          ) : (
            <LoadingState language={language} />
          )}

          <div className="left-rail">
            <ControlPanel
              language={language}
              elections={catalog.elections}
              geographyModes={catalog.geographyModes}
              electionId={electionId}
              geographyMode={geographyMode}
              onElectionChange={handleElectionChange}
              onGeographyModeChange={handleGeographyChange}
            />
            {activeView === 'party-map' ? (
              <PartyMapPanel
                language={language}
                parties={partyMapParties}
                selectedPartyId={effectivePartyId}
                upperBoundShare={partyMapUpperBoundShare}
                onPartyChange={setSelectedPartyId}
              />
            ) : null}
            {activeView === 'party-comparison' ? (
              <PartyComparisonPanel
                language={language}
                parties={partyMapParties}
                firstPartyId={effectiveComparisonFirstId}
                secondPartyId={effectiveComparisonSecondId}
                onFirstPartyChange={handleComparisonFirstChange}
                onSecondPartyChange={handleComparisonSecondChange}
              />
            ) : null}
            <GeographySearch
              language={language}
              electionId={electionId}
              geographyMode={geographyMode}
              items={searchIndex?.items ?? []}
              bounds={catalog.bounds}
              statisticalGeometryUrl={resolveDataUrl(
                selectedElection.geographiesByMode['statistical-area'].geometryUrl,
              )}
              loading={searchState.status === 'loading'}
              error={searchState.status === 'error' ? searchState.message : null}
              selectedItem={selectedSearchItem}
              selectedAddress={selectedAddress}
              onSelect={handleSearchSelect}
              onAddressSelect={handleAddressSearchSelect}
              onClearSelection={clearMapSelection}
            />
            <EnvelopeSummary
              language={language}
              record={results?.envelope ?? null}
              parties={results?.parties ?? []}
              selected={selectedId === results?.envelope?.id}
              onSelect={() => handleMapSelect(results?.envelope?.id ?? null)}
            />
            <DetailsPanel
              language={language}
              record={selectedRecord}
              emptySelection={
                selectedId === selectedSearchItem?.id && !selectedRecord
                  ? selectedSearchItem
                  : null
              }
              parties={results?.parties ?? []}
              highlightedPartyIds={
                activeView === 'party-comparison' &&
                effectiveComparisonFirstId &&
                effectiveComparisonSecondId
                  ? [effectiveComparisonFirstId, effectiveComparisonSecondId]
                  : []
              }
            />
          </div>
        </div>
      ) : (
        <NationalResultsScreen
          language={language}
          elections={catalog.elections}
          electionId={electionId}
          results={nationalResults}
          loading={nationalResultsState.status === 'loading'}
          error={
            nationalResultsState.status === 'error' ? nationalResultsState.message : null
          }
          onElectionChange={handleElectionChange}
        />
      )}
    </main>
  )
}

function safeStorage(): Storage | undefined {
  try {
    return window.localStorage
  } catch {
    return undefined
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
